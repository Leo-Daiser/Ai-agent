from __future__ import annotations 
from dataclasses import dataclass ,field 
from typing import List ,Dict ,Any 
import json 


@dataclass 
class TurnLog :
    turn_id :int 
    agent_visible_message :str 
    user_message :str 
    internal_thoughts :str 


@dataclass 
class InterviewLog :
    participant_name :str 
    position :str 
    grade :str 
    experience :str 
    turns :List [TurnLog ]=field (default_factory =list )
    final_feedback :str |None =None 

    def log_turn (self ,turn_id :int ,agent_visible_message :str ,user_message :str ,internal_thoughts :str )->None :
        self .turns .append (TurnLog (turn_id ,agent_visible_message ,user_message ,internal_thoughts ))

    def set_final_feedback (self ,feedback :str )->None :
        self .final_feedback =feedback 

    def to_dict (self )->Dict [str ,Any ]:
        return {
        "participant_name":self .participant_name ,
        "turns":[
        {
        "turn_id":t .turn_id ,
        "agent_visible_message":t .agent_visible_message ,
        "user_message":t .user_message ,
        "internal_thoughts":t .internal_thoughts ,
        }
        for t in self .turns 
        ],
        "final_feedback":self .final_feedback ,
        }

    def save (self ,filename :str )->None :
        with open (filename ,"w",encoding ="utf-8")as f :
            json .dump (self .to_dict (),f ,ensure_ascii =False ,indent =2 )
