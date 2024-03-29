from rest_framework import serializers
from .models import StudySession, Assessment, Mcq
import uuid
import os
import openai
import requests
import string
import dj_database_url
openai.organization = os.environ.get("ORG_KEY")
openai.api_key =os.environ.get("OPENAI_KEY")

import json
import ast

class StudySessionSerializer(serializers.ModelSerializer):
    created_at = serializers.CharField(required=False, read_only=True)
    pdf_url = serializers.CharField(required=False, read_only=True)
    finished_at = serializers.CharField(required=False, read_only=True)
    session_id = serializers.CharField(required=False, read_only=True)
    status = serializers.CharField(required=False, read_only=True)
    # session_name = serializers.CharField(required=False, read_only=True)
    class Meta:
        model = StudySession
        fields = ['session_name','session_id', 'pdf_file', 'pdf_url', 'created_at','finished_at','status']

    def create(self, data):        
        #data['session_name'] = 'some thing'  
        studysession= StudySession.objects.create(
            session_name = data.get("session_name"),
            pdf_file = data.get("pdf_file")
        )


        studysession.save()
        data['created_at'] = studysession.created_at
        data['session_id'] = studysession.session_id
        data['pdf_url'] = studysession.pdf_file.url
        data['status'] = 'Session Created Sucessfully '
        data['finished_at'] = 'Session not closed'
        # data['session_name'] = "Topic : " + studysession.pdf_file.url[7:-4] 
        # studysession.session_name = data['session_name']
        # studysession.save()
        return data
    
class AssessmentSerializer(serializers.ModelSerializer):
    status = serializers.CharField(required=False, read_only=True)
    score = serializers.DecimalField(required=False, read_only=True,max_digits=4, decimal_places=2)
    pdf_url = serializers.CharField(required=False, read_only=True)
    assessment_id = serializers.CharField(required=False, read_only=True)
    class Meta:
        model = Assessment
        fields = ['id','assessment_id','session_id','topic','score','pdf_url','status']
    
    def create(self, data):    
        session_uuid = uuid.UUID(data['session_id']) 

        data['score'] = 4
        current_session = StudySession.objects.get(session_id = session_uuid)
        data['pdf_url'] = current_session.pdf_file.url
        new_assessment = Assessment.objects.create(
            session_id = data['session_id'],
            assesment_id = current_session,
            topic = data['topic'],
            score = data['score'],
        )
        new_assessment.save()
        data['assessment_id'] = new_assessment.pk
        data['status'] = 'Assesment created Sucessfully'
        return data

class McqSerializer(serializers.ModelSerializer):
    gen_question = serializers.CharField(required=False, read_only=True)
    question = serializers.CharField(required=False, read_only=True)
    option_a = serializers.CharField(required=False, read_only=True)
    option_b = serializers.CharField(required=False, read_only=True)
    option_c = serializers.CharField(required=False, read_only=True)
    option_d = serializers.CharField(required=False, read_only=True)
    correct_answer = serializers.CharField(required=False, read_only=True)
    dif_score = serializers.CharField(required=False, read_only=True)
    status = serializers.CharField(required=False, read_only=True)
    class Meta:
         model = Mcq
         fields = ['id', 'assessment_id', 'gen_question','question','option_a','option_b','option_c','option_d','correct_answer', 'is_correct', 'time_taken', 'dif_score','status']

    def create(self, data):
        current_assessment = Assessment.objects.get(pk = data['assessment_id'])
        topic=current_assessment.topic
        diff = self.calc_mcq_score(data['is_correct'], data['time_taken'])
        req = self.get_next_quest(diff,topic)
        res = json.loads(req["content"])
        print(req["content"])
        mcq = Mcq.objects.all()

        if len(mcq) == 0 :

            new_mcq = Mcq.objects.create(
            assessment_id = data['assessment_id'],
            assesment= current_assessment,
            gen_question = "{'question': 'Dummy Question --> Ignore', 'options': {'a': 'print', 'b': 'range', 'c': 'sort', 'd': 'len'}, 'correct_answer': 'c'}",
            is_correct = data['is_correct'],
            time_taken = data['time_taken'],
            difficulty_score = diff,
                )
            
        else:
            prev_mcq = Mcq.objects.get(pk = len(mcq))
            prev_mcq.is_correct = data['is_correct']
            prev_mcq.time_taken = data['time_taken']
            current_assessment.score  = float(current_assessment.score) + float(diff)
            current_assessment.save()
            # prev_mcq.difficulty_score = diff       
            prev_mcq.save()
            

        data['gen_question'] = json.dumps(res)
        
        data['question'] = res['question']
        try:
            try: 
                data['option_a'] = res['options']['a']
                data['option_b'] = res['options']['b']
                data['option_c'] = res['options']['c']
                data['option_d'] = res['options']['d']
                data['correct_answer'] = res['correct_answer']

            except KeyError or TypeError:
                try:

                    data['option_a'] = res['options']['A']
                    data['option_b'] = res['options']['B']
                    data['option_c'] = res['options']['C']
                    data['option_d'] = res['options']['D']
                    data['correct_answer'] = res['correct_answer'].lower()
                except TypeError:
                    data['option_a'] = res['options'][0]
                    data['option_b'] = res['options'][1]
                    data['option_c'] = res['options'][2]
                    data['option_d'] = res['options'][3]
                    data['correct_answer'] = "a" if data['option_a'] == data['correct_answer'] else "b" if data['option_b'] == data['correct_answer'] else "c" if data['option_c'] == data['correct_answer'] else "d" 
        except KeyError or TypeError:
            self.create(data)
        
        data['dif_score'] = diff
        
        new_mcq = Mcq.objects.create(
            assessment_id = data['assessment_id'],
            assesment= current_assessment,
            gen_question = data['gen_question'],
            is_correct = data['is_correct'],
            time_taken = data['time_taken'],
            difficulty_score = diff,
        )
        new_mcq.save()
        data['status'] = 'Assesment created Sucessfully'
        return data

    def calc_mcq_score(self,is_correct, response_time):
        accuracy_weight = 5
        response_time_weight = 5
        max_response_time = 200  #200 seconds

        if is_correct:
            accuracy_score=5
        else:
            accuracy_score=0


        response_time_score = response_time_weight * (1 - min(response_time / max_response_time, 1))

        total_score = accuracy_score + response_time_score
        return total_score
    
    def get_next_quest(self, diff,topic):
        t="Give me an MCQ question from topic " + topic + " of difficulty " + str(diff) + "/10. Label correct answer as correct_answer. Give it in JSON format"

        prompt = t

        content=f"""Please give proper MCQ question"""
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
            {"role": "system", "content": content },
            {"role": "user", "content": prompt}
            ]
        )

        res=completion.choices[0].message
        return(res)
    


class PlotSerializer(serializers.ModelSerializer):
    easy = serializers.CharField(required=False, read_only=True)
    medium = serializers.CharField(required=False, read_only=True)
    hard = serializers.CharField(required=False, read_only=True)
    time_taken_easy = serializers.CharField(required=False, read_only=True)
    time_taken_hard = serializers.CharField(required=False, read_only=True)
    time_taken_medium = serializers.CharField(required=False, read_only=True)
    topics = serializers.CharField(required=False, read_only=True)



    class Meta:
        model = Assessment
        fields = ['session_id','easy','medium','hard','time_taken_easy','time_taken_medium','time_taken_hard', 'topics']
    
    def create(self,data):
        session_uuid = uuid.UUID(data['session_id']) 
        current_session = StudySession.objects.get(session_id = session_uuid)

        all_assessments = Assessment.objects.filter(assesment_id =current_session)
        topic_data = all_assessments.values_list('topic')

        print(topic_data)
        data['easy'] = "<QuerySet [('question-id-5',), ('question-id-3',)]>"
        data['medium'] = "<QuerySet [('question-id-7',), ('question-id-2',)]>"
        data['hard'] = "<QuerySet [('question-id-1',), ('question-id-4',)]>"
        data['time_taken_easy'] = "<QuerySet [('45',), ('10',)]>"
        data['time_taken_medium'] = "<QuerySet [('66',), ('34',)]>"
        data['time_taken_hard'] = "<QuerySet [('122',), ('33',)]>"
        data['topics'] = topic_data
        return data

        




