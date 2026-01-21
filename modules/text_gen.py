import os
import json
from openai import OpenAI

class TextGenerator:
    def __init__(self, api_key=None, base_url=None):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.base_url = base_url
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        else:
            self.client = None

    def _get_constraints(self, grade):
        """
        Derive constraints (vocabulary, grammar, length) based on the grade.
        """
        # Default settings
        constraints = {
            "vocab_level": "basic",
            "grammar_level": "simple sentences",
            "length_desc": "short (approx. 1-2 mins read)",
            "word_count": "100-150 words"
        }

        # Logic for implicit constraints
        if "小学" in grade or "Primary" in grade:
            constraints["vocab_level"] = "Primary School level (basic everyday words)"
            constraints["grammar_level"] = "Simple present/past tense, short sentences"
            if "Grade 1" in grade or "Grade 2" in grade:
                 constraints["word_count"] = "50-80 words"
            else:
                 constraints["word_count"] = "80-150 words"
        
        elif "初中" in grade or "Junior" in grade:
            constraints["vocab_level"] = "Junior High School level (common phrases, slight complexity)"
            constraints["grammar_level"] = "Compound sentences, basic clauses"
            # Specific requirement: Junior 2 -> 6 mins, Junior 3 -> 8 mins
            # 6 mins * 130 wpm = 780 words. 8 mins * 130 wpm = 1040 words.
            if "Grade 8" in grade or "初二" in grade:
                constraints["length_desc"] = "approx. 6 minutes reading time"
                constraints["word_count"] = "750-850 words"
            elif "Grade 9" in grade or "初三" in grade:
                constraints["length_desc"] = "approx. 8 minutes reading time"
                constraints["word_count"] = "950-1100 words"
            else: # Junior 1
                constraints["length_desc"] = "approx. 3-4 minutes reading time"
                constraints["word_count"] = "400-500 words"

        elif "高中" in grade or "Senior" in grade:
            constraints["vocab_level"] = "Senior High School level (academic, formal)"
            constraints["grammar_level"] = "Complex structures, subjunctive mood, various clauses"
            constraints["length_desc"] = "long (approx. 8-10 mins read)"
            constraints["word_count"] = "1000-1200 words"

        return constraints

    def generate_text(self, grade, interest):
        """
        Generates English text using Qwen/OpenAI API.
        """
        if not self.client:
            raise ValueError("API Key is missing. Please configure it in the sidebar.")

        constraints = self._get_constraints(grade)
        
        system_prompt = f"""You are an expert English teacher and content creator. 
        Your task is to write an educational English article for a student.
        
        Target Audience: {grade}
        Topic: {interest}
        
        Constraints:
        1. Vocabulary: {constraints['vocab_level']}
        2. Grammar: {constraints['grammar_level']}
        3. Length: {constraints['length_desc']} (Target word count: {constraints['word_count']})
        4. Style: Engaging, educational, and suitable for reading aloud (shadowing).
        5. Language: The content must be authentic American English.
        
        Important Note on Topic:
        If the user-provided topic '{interest}' is not in English (e.g., in Chinese), you MUST first translate it into idiomatic American English.
        Use the translated English topic as the title and subject of the article.
        
        Output Format:
        Return ONLY a raw JSON object (no markdown formatting) with the following structure:
        {{
            "title": "Title of the article (in English)",
            "content": "The full article text (in authentic American English)...",
            "keywords": ["word1", "word2", "word3"],
            "chinese_translation": ["词义1", "词义2", "词义3"],
            "analysis": {{
                "vocabulary": [
                    {{ "word": "word1", "pos": "noun", "meaning": "中文释义" }},
                    ...
                ],
                "grammar": [
                    {{ "point": "Grammar rule", "example": "Example sentence" }},
                    ...
                ],
                "expressions": [
                    {{ "phrase": "phrase1", "replacement": "alternative", "scenario": "usage scenario" }},
                    ...
                ],
                "easy_test": [
                    {{ "question": "Question 1?", "options": ["A", "B", "C", "D"], "answer": "A", "explanation": "Why A is correct" }},
                    ...
                ],
                "shadowing_sentences": [
                    "Sentence 1 (Key sentence from text)...",
                    "Sentence 2...",
                    "Sentence 3...",
                    "Sentence 4...",
                    "Sentence 5..."
                ]
            }}
        }}
        """

        user_prompt = f"""Please write an article about '{interest}' for a student in {grade}. strictly following the length constraint of {constraints['word_count']}.

        After generating the article, act as a senior English teacher familiar with FLTRP (外研社) textbooks for {grade}. 
        Extract key vocabulary, phrases, grammar points, and expressions suitable for this level from the generated text.
        Also, generate 3 easy multiple-choice questions (Easy Test) to test understanding of vocabulary or grammar.
        
        Analysis Requirements:
        1. Vocabulary & Phrases: List 3-5 key words/phrases with part of speech and Chinese meaning.
        2. Grammar Points: List 2-3 key grammar points with examples.
        3. Expressions: List 2-3 key expressions with replacements and usage scenarios.
        4. Easy Test: Create 3 multiple-choice questions with answer keys and brief explanations.
        5. Shadowing Sentences: Extract exactly 5 key sentences from the generated article that are suitable for practicing intonation and pronunciation. These should be complete, representative sentences.
        
        Put this structured analysis into the 'analysis' field of the JSON response, following the Output Format structure exactly.
        """

        try:
            response = self.client.chat.completions.create(
                model="qwen-turbo", # Default to qwen-turbo or let user config. Using a safe default for Qwen.
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"} # Ensure JSON output
            )
            
            content_str = response.choices[0].message.content
            return json.loads(content_str)
            
        except Exception as e:
            # Fallback if model doesn't support json_object or specific model name error
            # Try parsing manually if needed, but for now just re-raise with clarity
            raise Exception(f"API Error: {str(e)}")
