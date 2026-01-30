
from __future__ import annotations 

import os 
from typing import List ,Dict ,Optional ,Any 
import re 
import importlib 





def _load_mistral_sdk ():
    try :
        return importlib .import_module ("mistralai")
    except ImportError :
        return None 


_MISTRAL_CLIENT :Any =None 


def _get_mistral_client ():
    global _MISTRAL_CLIENT 
    if _MISTRAL_CLIENT is not None :
        return _MISTRAL_CLIENT 

    mistral =_load_mistral_sdk ()
    if mistral is None :
        raise RuntimeError (
        "Package 'mistralai' is not installed. Install it with: pip install mistralai"
        )

    api_key =os .getenv ("MISTRAL_API_KEY")
    if not api_key :
        raise RuntimeError (
        "MISTRAL_API_KEY environment variable is not set. "
        "Create a key in the Mistral Console and put it into .env."
        )


    if hasattr (mistral ,"Mistral"):
        _MISTRAL_CLIENT =mistral .Mistral (api_key =api_key )
        return _MISTRAL_CLIENT 


    try :
        client_mod =importlib .import_module ("mistralai.client")
        if hasattr (client_mod ,"MistralClient"):
            _MISTRAL_CLIENT =client_mod .MistralClient (api_key =api_key )
            return _MISTRAL_CLIENT 
    except Exception :
        pass 

    raise RuntimeError (
    "Installed 'mistralai' package does not expose a supported client. "
    "Please upgrade: pip install -U mistralai"
    )


def call_llm (
system_prompt :str ,
messages :List [Dict [str ,str ]],
temperature :float =0.2 ,
model :Optional [str ]=None ,
)->str :
    client =_get_mistral_client ()
    chosen_model =model or os .getenv ("MISTRAL_MODEL","mistral-medium-latest")

    chat_messages =[{"role":"system","content":system_prompt }]+messages 


    if hasattr (client ,"chat"):
        chat =getattr (client ,"chat")
        if hasattr (chat ,"complete"):
            resp =chat .complete (
            model =chosen_model ,
            messages =chat_messages ,
            temperature =float (temperature ),
            )

            try :
                return resp .choices [0 ].message .content .strip ()
            except Exception :
                pass 

        if callable (chat ):
            resp =chat (
            model =chosen_model ,
            messages =chat_messages ,
            temperature =float (temperature ),
            )
            try :
                return resp .choices [0 ].message .content .strip ()
            except Exception :
                pass 

    raise RuntimeError ("Mistral returned an empty/unsupported response format.")


class ObserverAgent :

    def __init__ (
    self ,
    position :str |None =None ,
    grade :str |None =None ,
    experience :str |None =None ,
    )->None :
        self .difficulty =1 
        self .performance_score =0 
        self .questions_asked :List [Dict [str ,Any ]]=[]

        self .last_evaluation_result :Optional [str ]=None 
        self .position =position 
        self .grade =grade 
        self .experience =experience 
        self .recent_turns :List [Dict [str ,Any ]]=[]
        self .profile_inferred =False 
        self .profile_position :str |None =None 
        self .profile_topics :List [str ]=[]
        self .profile_grade :str |None =None 

    @staticmethod 
    def _parse_json_response (raw :str )->Dict [str ,Any ]:
        import json 
        import re 

        raw_clean =raw .strip ()
        if raw_clean .startswith ("```"):
            first_nl =raw_clean .find ("\n")
            if first_nl !=-1 :
                raw_clean =raw_clean [first_nl +1 :]
            if raw_clean .rstrip ().endswith ("```"):
                raw_clean =raw_clean .rstrip ()[:-3 ].rstrip ()
        try :
            return json .loads (raw_clean )
        except json .JSONDecodeError :
            match =re .search (r"\{.*\}",raw_clean ,re .DOTALL )
            if match :
                return json .loads (match .group (0 ))
            raise 

    @staticmethod 
    def _parse_llm_json (raw :str )->Dict [str ,Any ]:
        return ObserverAgent ._parse_json_response (raw )

    def infer_profile_from_intro (self ,candidate_answer :str )->Dict [str ,Any ]:
        system_prompt =(
        "Вы — технический интервьюер. На основе ответа кандидата определите:\n"
        "1) Позицию (должность) кандидата.\n"
        "2) 4-7 релевантных тем для технических вопросов по этой позиции.\n"
        "3) Предполагаемый грейд (Junior/Middle/Senior).\n"
        "Верните СТРОГО JSON: {\"position\": \"...\", \"topics\": [\"...\"], \"grade\": \"...\"}.\n"
        "Если кандидат упоминает DevOps/SRE/Infrastructure, включайте темы: Linux, сети, CI/CD, облака, "
        "контейнеры, мониторинг/логирование, IaC, безопасность. "
        "Если упоминает Frontend, включайте темы: JS/TS, HTML/CSS, браузер, React/Vue, производительность.\n"
        "Если упоминает Backend, включайте темы: API, базы данных, архитектура, кэширование, очереди.\n"
        "Если информации мало, сделайте лучший вывод, но не добавляйте нерелевантные темы."
        )
        messages =[
        {
        "role":"user",
        "content":f"Ответ кандидата: {candidate_answer}",
        }
        ]
        raw =call_llm (system_prompt ,messages ,temperature =0 )
        try :
            data =self ._parse_llm_json (raw )
        except Exception :
            data ={}
        position =data .get ("position","").strip ()
        raw_topics =data .get ("topics",[])
        if isinstance (raw_topics ,str ):
            topics =[t .strip ()for t in raw_topics .split (",")if t .strip ()]
        else :
            topics =[t .strip ()for t in raw_topics if isinstance (t ,str )and t .strip ()]
        grade =data .get ("grade","").strip ()

        if not topics :
            topics =["основы инженерии ПО"]
        if not grade :
            grade ="Junior"

        self .profile_inferred =True 
        self .profile_position =position or (self .position or "не указано")
        self .profile_topics =topics 
        self .profile_grade =grade 
        self .difficulty =self ._grade_to_difficulty (grade )
        return {
        "position":self .profile_position ,
        "topics":self .profile_topics ,
        "grade":self .profile_grade ,
        }

    @staticmethod 
    def _grade_to_difficulty (grade :str )->int :
        grade_lower =grade .lower ()
        if grade_lower .startswith ("junior")or grade_lower .startswith ("джун"):
            return 1 
        if grade_lower .startswith ("middle")or grade_lower .startswith ("мид"):
            return 2 
        if grade_lower .startswith ("senior")or grade_lower .startswith ("сеньор"):
            return 3 
        return 1 

    def record_turn (self ,question :Dict [str ,Any ],candidate_answer :str ,evaluation :Dict [str ,Any ])->None :
        self .recent_turns .append (
        {
        "question":question .get ("question",""),
        "topic":question .get ("topic",""),
        "candidate_answer":candidate_answer ,
        "result":evaluation .get ("result","unknown"),
        }
        )

        self .recent_turns =self .recent_turns [-6 :]

    def evaluate_answer (self ,question :Dict [str ,Any ],candidate_answer :str )->Dict [str ,Any ]:

        answer_norm =candidate_answer .strip ().lower ()




        question_words =[
        "что",
        "как",
        "когда",
        "зачем",
        "почему",
        "какой",
        "какие",
        "кто",
        "сколько",
        ]

        if "?"in candidate_answer :
            stripped =candidate_answer .strip ().lower ()

            if stripped .endswith ("?")or any (stripped .startswith (w )for w in question_words ):
                self .last_evaluation_result ="role_reversal"
                return {
                "result":"role_reversal",
                "reason":"Кандидат задал встречный вопрос. Нужно ответить и продолжить интервью.",
                "confidence":90 ,
                "correct_answer":question ["answer"],
                "topics":[],
                }


        off_topic_keywords =[
        "погода",
        "weather",
        "кошка",
        "собака",
        "ха ха",
        "не по теме",
        ]
        for kw in off_topic_keywords :
            if kw in answer_norm :
                self .last_evaluation_result ="off_topic"
                return {
                "result":"off_topic",
                "reason":"Ответ не относится к заданному техническому вопросу.",
                "confidence":90 ,
                "correct_answer":question ["answer"],
                "topics":[],
                }


        hallucination_patterns =[
        r"python\s*4\.0",
        r"уберут\s+циклы",
        r"нейронные\s+связи",
        r"magic is real",
        ]
        for pat in hallucination_patterns :
            if re .search (pat ,answer_norm ):
                self .last_evaluation_result ="hallucination"
                return {
                "result":"hallucination",
                "reason":"Ответ содержит ложные утверждения, не подтверждённые фактом.",
                "confidence":90 ,
                "correct_answer":question ["answer"],
                "topics":[],
                }


        system_prompt =(
        "Вы — помощник для оценки ответов кандидатов на технические вопросы. "
        "Вам дан вопрос, ожидаемый правильный ответ и фактический ответ кандидата. "
        "Классифицируйте ответ как 'correct', 'partial' или 'incorrect'. "
        "Также укажите краткую причину и уверенность (0-100). "
        "Верните СТРОГО JSON: {\"result\": ..., \"reason\": ..., \"confidence\": ...}."
        )
        messages =[
        {
        "role":"user",
        "content":(
        f"Позиция: {self.profile_position or self.position or 'не указано'}\n"
        f"Тема вопроса: {question.get('topic', 'не указано')}\n"
        f"Вопрос: {question['question']}\n"
        f"Ожидаемый ответ: {question['answer']}\n"
        f"Ответ кандидата: {candidate_answer}\n"
        ),
        }
        ]
        raw =call_llm (system_prompt ,messages ,temperature =0 )
        data =self ._parse_llm_json (raw )
        result =data ["result"]
        reason =data .get ("reason","")
        try :
            confidence =int (data .get ("confidence",60 ))
        except (TypeError ,ValueError ):
            confidence =60 


        self .last_evaluation_result =result 
        return {
        "result":result ,
        "reason":reason ,
        "confidence":max (0 ,min (confidence ,100 )),
        "correct_answer":question ["answer"],
        "topics":[question .get ("topic","")],
        }

    def update_difficulty (self ,evaluation_result :str )->None :
        if evaluation_result =="correct":
            self .performance_score +=1 
            if self .performance_score %2 ==0 :
                self .difficulty =min (3 ,self .difficulty +1 )
        elif evaluation_result in ("incorrect","partial"):
            self .performance_score =max (0 ,self .performance_score -1 )
            if self .performance_score %2 ==1 and self .performance_score >0 :
                self .difficulty =max (1 ,self .difficulty -1 )


    def select_next_question (self )->Dict [str ,Any ]:
        if not self .profile_inferred :
            return self ._generate_intro_question_via_llm ()

        q =self ._generate_question_via_llm ()


        if "difficulty"not in q :
            q ["difficulty"]=self .difficulty 
        if "topic"not in q or q ["topic"]not in self .profile_topics :
            q ["topic"]=self .profile_topics [0 ]



        self .questions_asked .append (q )
        return q 

    def _generate_intro_question_via_llm (self )->Dict [str ,Any ]:
        system_prompt =(
        "Вы — интервьюер. Сформулируйте краткий первый вопрос, "
        "чтобы кандидат представился, указал позицию, опыт и ключевые технологии. "
        "Верните СТРОГО JSON: {\"question\": \"...\"}."
        )
        messages =[{"role":"user","content":"Сгенерируйте первое приветственное обращение."}]
        raw =call_llm (system_prompt ,messages ,temperature =0 )
        try :
            data =self ._parse_llm_json (raw )
            question_text =data .get ("question","").strip ()
        except Exception :
            question_text =""
        if not question_text :
            question_text ="Расскажите о себе, о вашей роли и опыте."
        return {
        "topic":"intro",
        "difficulty":1 ,
        "question":question_text ,
        "answer":"",
        }

    def _generate_question_via_llm (self )->Dict [str ,Any ]:

        system_prompt =(
        "Вы — ассистент по проведению технических собеседований. "
        "Сгенерируйте следующий вопрос для кандидата на основе предоставленной информации. "
        "Вы должны вернуть JSON со следующими полями: 'topic' (одна из тем: "
        f"{', '.join(self.profile_topics)}"+"), 'difficulty' (целое 1-3), "
        "'question' (текст вопроса на русском языке), 'answer' (ожидаемый правильный краткий ответ). "
        "Выбирайте тему только из списка допустимых и придерживайтесь указанной сложности. "
        "Если предыдущий ответ кандидата был верным, вы можете увеличить сложность; "
        "если неверным — уменьшить. Вопросы должны строго соответствовать позиции кандидата."
        )

        perf =self .last_evaluation_result or "none"
        asked =[q .get ("question","")for q in self .questions_asked [-5 :]]
        recent_context =[
        f"{idx + 1}) Q: {t['question']} | A: {t['candidate_answer']} | R: {t['result']}"
        for idx ,t in enumerate (self .recent_turns [-4 :])
        ]
        user_content =(
        f"Позиция кандидата: {self.profile_position or 'не указано'}\n"
        f"Темы: {', '.join(self.profile_topics)}\n"
        f"Желаемая сложность: {self.difficulty}\n"
        f"Последняя оценка ответа кандидата: {perf}\n"
        f"Контекст последних ответов кандидата (не повторять вопросы): {recent_context}\n"
        f"Уже заданные вопросы (не повторять): {asked}\n"
        "Сгенерируйте ОДИН новый вопрос, который НЕ повторяет уже заданные."
        )
        messages =[{"role":"user","content":user_content }]
        raw =call_llm (system_prompt ,messages ,temperature =0 )
        try :
            question_dict =self ._parse_llm_json (raw )

            for key in ("topic","question","answer"):
                if key not in question_dict :
                    raise ValueError (f"Missing key {key} in LLM response")
            return question_dict 
        except Exception as e :
            raise RuntimeError (f"Failed to parse LLM question JSON: {e}. Raw response: {raw}")


class InterviewerAgent :

    def __init__ (self )->None :
        pass 

    def pose_question (self ,question :Dict [str ,Any ])->str :
        return question ["question"]

    def handle_off_topic_or_hallucination (self ,evaluation_result :str )->str :
        if evaluation_result =="off_topic":
            return "Ваш ответ не связан с вопросом. Давайте вернёмся к теме и попробуем ещё раз."
        elif evaluation_result =="hallucination":
            return (
            "Похоже, ответ содержит неправдоподобные утверждения. Пожалуйста, попробуйте дать фактологический ответ."
            )
        else :
            return ""

    def handle_role_reversal (self ,candidate_question :str )->str :

        system_prompt =(
        "Вы — рекрутер, отвечающий на вопросы кандидатов во время интервью. "
        "Ответьте кратко и по существу на вопрос кандидата о работе, команде, технологиях или процессах. "
        "Если вопрос выходит за рамки вашей компетенции, вежливо скажите, что уточните у команды."
        )
        messages =[
        {
        "role":"user",
        "content":f"Вопрос кандидата: {candidate_question}\nКратко ответьте."
        }
        ]
        reply =call_llm (system_prompt ,messages ,temperature =0 )
        return reply 

    def acknowledge_answer (self ,evaluation_result :str )->str :
        if evaluation_result =="correct":
            return "Спасибо! Давайте перейдём к следующему вопросу."
        elif evaluation_result =="partial":
            return "Ответ частично верный. Продолжим интервью."
        else :
            return "Спасибо за ответ. Перейдём к следующему вопросу."
