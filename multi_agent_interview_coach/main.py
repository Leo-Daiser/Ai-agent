
from __future__ import annotations 

import re 
from typing import List ,Dict ,Any 
from pathlib import Path 

from .logger import InterviewLog 
from .agents import ObserverAgent ,InterviewerAgent 
from dotenv import load_dotenv 

load_dotenv (dotenv_path =Path (__file__ ).resolve ().parents [1 ]/".env")

class InterviewSession :

    def __init__ (
    self ,
    candidate_name :str ,
    position :str ,
    grade :str ,
    experience :str ,
    )->None :


        self .observer =ObserverAgent (
        position =position ,
        grade =grade ,
        experience =experience ,
        )
        self .interviewer =InterviewerAgent ()
        self .log =InterviewLog (
        participant_name =candidate_name ,
        position =position ,
        grade =grade ,
        experience =experience ,
        )
        self .turn_id =1 
        self .pending_question :Dict [str ,Any ]|None =None 
        self .evaluations :List [Dict [str ,Any ]]=[]

    def run (self )->None :
        print (f"Привет, {self.log.participant_name}! Давайте начнем техническое интервью.")
        while True :

            if self .pending_question is not None :
                question =self .pending_question 
                self .pending_question =None 
            else :
                question =self .observer .select_next_question ()
            visible_message =self .interviewer .pose_question (question )

            internal_before =(
            f"[Observer]: Задаём вопрос по теме '{question['topic']}' сложностью {self.observer.difficulty}. "
            "[Interviewer]: Озвучиваю вопрос кандидату."
            )

            print (f"\nВопрос {self.turn_id}: {visible_message}")
            candidate_answer =input ("Ваш ответ: ")

            stop_patterns =[
            r"\bстоп\b",
            r"\bстоп интервью\b",
            r"\bstop\b",
            r"\bstop interview\b",
            r"\bстоп игра\b",
            r"\bдавай фидбэк\b",
            r"\bfeedback\b",
            ]
            normalized_answer =candidate_answer .strip ().lower ()
            if any (re .search (pattern ,normalized_answer )for pattern in stop_patterns ):
                print ("Прерываем интервью и формируем отчёт...\n")
                break 

            if not self .observer .profile_inferred :
                profile =self .observer .infer_profile_from_intro (candidate_answer )
                internal_profile =(
                "[Observer]: Определён профиль кандидата: "
                f"{profile['position']}, темы: {', '.join(profile['topics'])}, "
                f"ориентировочный грейд: {profile['grade']}."
                )
                self .log .log_turn (
                self .turn_id ,
                visible_message ,
                candidate_answer ,
                internal_before +" "+internal_profile ,
                )
                self .turn_id +=1 
                continue 


            evaluation =self .observer .evaluate_answer (question ,candidate_answer )
            self .observer .record_turn (question ,candidate_answer ,evaluation )
            self .evaluations .append (
            {
            "question":question ["question"],
            "topic":question ["topic"],
            "candidate_answer":candidate_answer ,
            "result":evaluation ["result"],
            "correct_answer":evaluation ["correct_answer"],
            "reason":evaluation .get ("reason",""),
            "difficulty":question .get ("difficulty",self .observer .difficulty ),
            "confidence":evaluation .get ("confidence",0 ),
            }
            )

            self .observer .update_difficulty (evaluation ["result"])


            if evaluation ["result"]=="correct":
                recommendation ="усложнить"
            elif evaluation ["result"]in ("incorrect","partial"):
                recommendation ="упростить"
            elif evaluation ["result"]=="role_reversal":
                recommendation ="ответить кандидату и продолжить"
            else :

                recommendation ="повторить"
            internal_after =(
            f"[Observer]: Ответ классифицирован как {evaluation['result']}. "
            f"Рекомендация: {recommendation} вопрос."
            )
            internal_thoughts =internal_before +" "+internal_after 

            if evaluation ["result"]in ("off_topic","hallucination"):
                reply_to_candidate =self .interviewer .handle_off_topic_or_hallucination (evaluation ["result"])
                print (reply_to_candidate )

                self .log .log_turn (
                self .turn_id ,
                visible_message +"\n"+reply_to_candidate ,
                candidate_answer ,
                internal_thoughts ,
                )

                self .pending_question =question 
                continue 
            elif evaluation ["result"]=="role_reversal":

                reply =self .interviewer .handle_role_reversal (candidate_answer )
                print (reply )

                self .log .log_turn (
                self .turn_id ,
                visible_message +"\n"+reply ,
                candidate_answer ,
                internal_thoughts ,
                )

                self .turn_id +=1 
                continue 
            else :

                ack =self .interviewer .acknowledge_answer (evaluation ["result"])
                print (ack )

                self .log .log_turn (
                self .turn_id ,
                visible_message +"\n"+ack ,
                candidate_answer ,
                internal_thoughts ,
                )
                self .turn_id +=1 


        final_report =self .generate_final_feedback ()
        self .log .set_final_feedback (final_report )

        filename ="interview_log.json"
        self .log .save (filename )
        print (f"Лог интервью сохранён в {filename}.")
        print ("\nФинальный отчёт:\n")
        print (final_report )

    def generate_final_feedback (self )->str :
        return self ._build_structured_feedback ()

    def _build_structured_feedback (self )->str :
        scored =[e for e in self .evaluations if e ["result"]in ("correct","partial","incorrect")]
        confirmed =[e for e in scored if e ["result"]=="correct"]
        gaps =[e for e in scored if e ["result"]in ("incorrect","partial")]
        hallucinations =[e for e in self .evaluations if e ["result"]=="hallucination"]
        off_topic =[e for e in self .evaluations if e ["result"]=="off_topic"]
        role_reversal =[e for e in self .evaluations if e ["result"]=="role_reversal"]

        total =len (scored )
        score =sum (1 for e in scored if e ["result"]=="correct")+0.5 *sum (
        1 for e in scored if e ["result"]=="partial"
        )
        accuracy =score /total if total else 0.0 
        avg_difficulty =(
        sum (e .get ("difficulty",self .observer .difficulty )for e in scored )/total 
        if total 
        else self .observer .difficulty 
        )
        avg_confidence =(
        sum (e .get ("confidence",0 )for e in scored )/total 
        if total 
        else 0 
        )

        grade =self .observer .profile_grade or self .log .grade or "Junior"
        if total :
            if avg_difficulty >=3 and accuracy >=0.8 :
                grade ="Senior"
            elif avg_difficulty >=2 and accuracy >=0.65 :
                grade ="Middle"
            else :
                grade ="Junior"

        if total ==0 :
            hire_reco ="No Hire"
        elif accuracy >=0.85 and not hallucinations :
            hire_reco ="Strong Hire"
        elif accuracy >=0.65 and len (hallucinations )<=1 :
            hire_reco ="Hire"
        else :
            hire_reco ="No Hire"

        base_confidence =30 +total *5 
        confidence =(
        base_confidence 
        +int (accuracy *50 )
        +int ((avg_difficulty -1 )*10 )
        +int (avg_confidence *0.2 )
        )
        confidence -=len (hallucinations )*10 
        if total ==0 :
            confidence =20 
        confidence =max (20 ,min (90 ,confidence ))

        def clarity_label ()->str :
            if not scored :
                return "Недостаточно данных"
            avg_words =sum (len (e ["candidate_answer"].split ())for e in scored )/total 
            if avg_words >=20 :
                return "Высокая"
            if avg_words >=8 :
                return "Средняя"
            return "Низкая"

        def honesty_label ()->str :
            if hallucinations :
                return "Есть сомнительные/ложные утверждения"
            if any (
            phrase in e ["candidate_answer"].lower ()
            for e in gaps 
            for phrase in ("не знаю","затрудняюсь","не уверен")
            ):
                return "Честно признавал незнание"
            return "Нейтральная"

        engagement_label ="Задавал встречные вопросы"if role_reversal else "Нейтральная"

        lines =[
        f"Позиция: {self.observer.profile_position or self.log.position}",
        "A. Вердикт",
        f"- Грейд: {grade}",
        f"- Рекомендация по найму: {hire_reco}",
        f"- Уверенность: {confidence}%",
        "",
        "B. Анализ технических навыков",
        "✅ Подтверждённые навыки:",
        ]
        if confirmed :
            for entry in confirmed :
                lines .append (f"- {entry['topic']}: {entry['question']}")
        else :
            lines .append ("- Нет подтверждённых тем.")

        lines .append ("❌ Пробелы в знаниях:")
        if gaps :
            for entry in gaps :
                lines .append (f"- {entry['topic']}: {entry['question']}")
                lines .append (f"  Правильный ответ: {entry['correct_answer']}")
        else :
            lines .append ("- Существенных пробелов не выявлено.")

        lines .extend (
        [
        "",
        "C. Коммуникация и поведенческие сигналы",
        f"- Ясность: {clarity_label()}",
        f"- Честность: {honesty_label()}",
        f"- Вовлечённость: {engagement_label}",
        ]
        )
        if off_topic :
            lines .append ("- Уход от темы: были уходы в сторону, интервьюеру приходилось возвращать к вопросу.")

        lines .extend (
        [
        "",
        "D. План развития",
        ]
        )
        if gaps :
            seen_topics =set ()
            for entry in gaps :
                topic =entry ["topic"]
                if topic in seen_topics :
                    continue 
                seen_topics .add (topic )

                lines .append (f"- {topic}:")
                question =entry .get ("question","")
                correct =entry .get ("correct_answer","")

                if question :
                    lines .append (f"  Контрольный вопрос: {question}")
                if correct :
                    lines .append (f"  Что нужно уметь объяснить: {correct}")

                lines .append ("  Практика на 1–2 часа:")
                lines .append ("  - перечитать конспект/документацию и выписать 10 ключевых терминов")
                lines .append ("  - решить 3–5 задач или написать мини‑пример кода по теме")
                lines .append ("  - повторить через день: кратко пересказать тему без подсказок")
        else :
            lines .append ("- Сохранить темп: усложнять вопросы и углублять сильные темы.")

        return "\n".join (lines)


def main ()->None :
    print ("==== Multi‑Agent Interview Coach ====")
    name =input ("Введите имя кандидата: ")
    position =input ("Введите позицию (например, Backend Developer): ")
    grade =input ("Введите ожидаемый грейд (Junior/Middle/Senior): ")
    experience =input ("Опишите опыт кандидата: ")
    session =InterviewSession (name ,position ,grade ,experience )
    session .run ()


if __name__ =="__main__":
    main ()
