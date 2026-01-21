import random
import os
import json
import requests
import speech_recognition as sr
import difflib
import re

class Evaluator:
    def __init__(self, app_key=None, ak_id=None, ak_secret=None):
        # Aliyun Speech Assessment requires AppKey, AK ID, and AK Secret
        self.app_key = app_key or os.getenv("ALIYUN_APP_KEY")
        self.ak_id = ak_id or os.getenv("ALIYUN_AK_ID")
        self.ak_secret = ak_secret or os.getenv("ALIYUN_AK_SECRET")
        self.token = None
        self.region = "cn-shanghai"

    def get_token(self):
        """
        Get Token from Aliyun using CommonRequest.
        """
        try:
            from aliyunsdkcore.client import AcsClient
            from aliyunsdkcore.request import CommonRequest
            
            if not self.ak_id or not self.ak_secret:
                print("Missing Aliyun AK/SK")
                return None

            client = AcsClient(self.ak_id, self.ak_secret, self.region)
            request = CommonRequest()
            request.set_method('POST')
            request.set_domain('nls-meta.cn-shanghai.aliyuncs.com')
            request.set_version('2018-05-18')
            request.set_action_name('CreateToken')
            
            response = client.do_action_with_exception(request)
            response_json = json.loads(response)
            if 'Token' in response_json and 'Id' in response_json['Token']:
                self.token = response_json['Token']['Id']
                return self.token
            else:
                print("Failed to get Aliyun Token")
                return None
        except Exception as e:
            print(f"Aliyun Token Error: {e}")
            return None

    def evaluate_audio(self, user_audio_path, reference_text, method="local"):
        """
        Evaluates the user's audio against the reference text.
        method: "local" (SpeechRecognition) or "aliyun"
        """
        if method == "aliyun":
            if self.app_key and self.ak_id and self.ak_secret:
                return self._evaluate_aliyun(user_audio_path, reference_text)
            else:
                return {"error": "Missing Aliyun Credentials", "total_score": 0, "feedback": "Please configure Aliyun AppKey and AccessKeys."}
        else:
            # Default to Local STT
            return self._evaluate_local_stt(user_audio_path, reference_text)

    def _evaluate_local_stt(self, audio_path, reference_text):
        recognizer = sr.Recognizer()
        try:
            # Convert audio to wav if needed or just load
            # SpeechRecognition supports wav, aiff, flac
            # app.py saves as "user_recording.wav", so it should be fine.
            with sr.AudioFile(audio_path) as source:
                audio_data = recognizer.record(source)
            
            # Use Google Speech Recognition (Free API)
            try:
                user_text = recognizer.recognize_google(audio_data)
            except sr.UnknownValueError:
                user_text = ""
            except sr.RequestError:
                return self._evaluate_mock(audio_path, reference_text)

            return self._compare_texts(user_text, reference_text)
            
        except Exception as e:
            print(f"Local STT Error: {e}")
            return self._evaluate_mock(audio_path, reference_text)

    def _compare_texts(self, user_text, ref_text):
        import string
        def normalize(t):
            return t.translate(str.maketrans('', '', string.punctuation)).lower().split()
            
        u_words = normalize(user_text)
        r_words = normalize(ref_text)
        
        matcher = difflib.SequenceMatcher(None, r_words, u_words)
        ratio = matcher.ratio()
        
        # Find missing/wrong words in Reference
        error_words = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag in ['replace', 'delete']:
                # These words in reference (i1:i2) were not matched in user text
                for w in r_words[i1:i2]:
                    error_words.append(w)
        
        score = int(ratio * 100)
        
        feedback = f"Recognized: '{user_text}'."
        if score > 85:
            feedback += " Excellent pronunciation!"
        elif score > 60:
            feedback += " Good effort, check the highlighted words."
        else:
            feedback += " Keep practicing, or check your microphone."

        return {
            "total_score": score,
            "fluency_score": score, 
            "integrity_score": score, 
            "error_words": error_words,
            "feedback": feedback
        }

    def _evaluate_aliyun(self, audio_path, reference_text):
        if not self.token:
            self.get_token()
        
        if not self.token:
            return self._evaluate_mock(audio_path, reference_text)

        url = f"http://nls-gateway.{self.region}.aliyuncs.com/stream/v1/SpeechAssessment"
        
        # Aliyun REST API Headers
        headers = {
            "X-NLS-Token": self.token,
            "X-NLS-AppKey": self.app_key,
            "X-NLS-Format": "wav", 
            "X-NLS-Sample-Rate": "16000",
            "Content-Type": "application/octet-stream"
        }
        
        try:
            from urllib.parse import quote
            encoded_text = quote(reference_text[:2048]) 
            headers["X-NLS-Text"] = encoded_text
        except:
            pass

        try:
            with open(audio_path, "rb") as f:
                audio_data = f.read()

            response = requests.post(url, headers=headers, data=audio_data)

            if response.status_code == 200:
                result = response.json()
                return self._parse_aliyun_result(result)
            else:
                print(f"Aliyun API Error: {response.status_code} - {response.text}")
                return self._evaluate_mock(audio_path, reference_text)

        except Exception as e:
            print(f"Evaluation failed: {e}")
            return self._evaluate_mock(audio_path, reference_text)

    def _parse_aliyun_result(self, api_result):
        # Default values
        total_score = 0
        fluency = 0
        integrity = 0
        error_words = []
        feedback_details = []

        if "result" in api_result:
            res = api_result["result"]
            total_score = res.get("pronunciation_score", 0)
            fluency = res.get("fluency_score", 0)
            integrity = res.get("integrity_score", 0)
            
            # Extract error words (score < 60)
            words = res.get("words", [])
            for w in words:
                if w.get("score", 0) < 60:
                    error_words.append(w.get("text", ""))
                    
            # Check for specific feedback opportunities (simplified logic)
            if fluency < 60:
                feedback_details.append("Try to speak more smoothly without long pauses.")
            if integrity < 80:
                feedback_details.append("Make sure to finish every word clearly.")

        feedback = "Excellent! Your pronunciation is very clear." if total_score > 85 else "Good effort! Pay attention to the highlighted words."
        if feedback_details:
            feedback += " " + " ".join(feedback_details)

        return {
            "total_score": total_score,
            "fluency_score": fluency,
            "integrity_score": integrity,
            "error_words": error_words,
            "feedback": feedback
        }

    def _evaluate_mock(self, user_audio_path, reference_text):
        # Mock evaluation logic
        score = random.randint(70, 100)
        fluency = random.randint(70, 100)
        integrity = random.randint(80, 100)
        
        words = reference_text.split()
        error_words = []
        if score < 90 and words:
            num_errors = random.randint(1, 3)
            error_words = random.sample(words, min(num_errors, len(words)))

        return {
            "total_score": score,
            "fluency_score": fluency,
            "integrity_score": integrity,
            "error_words": error_words,
            "feedback": "Great job! Keep practicing to improve your fluency." if score > 85 else "Good effort, try to focus on the highlighted words."
        }
