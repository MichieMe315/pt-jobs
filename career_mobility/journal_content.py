"""Editable professional worksheets. Prompts organize practice; they do not prescribe care."""
from .journal_editions import EDITIONS

# Each edition has its own six-page sequence. These titles also label the editor navigator.
WORKSHEETS = {
 'oncology': [
  ('Care context', 'Build a working picture before planning a rehabilitation visit.', [('Treatment context','What treatment phase, recent changes and information from the care team matter for this visit?'),('Daily life and priorities','Which activities, roles and routines does the person want to maintain or return to?'),('Questions to clarify','What information or documented precautions do you need to confirm with the appropriate clinician?'),('Visit focus','Which agreed functional priority will guide the session?')]),
  ('Activity and fatigue', 'Describe patterns and responses without reducing the person to a score.', [('Energy through the day','When are activities easier or harder, and what pattern has the person noticed?'),('Activity record','Record the activity, duration or amount, and the context in which it took place.'),('Response and recovery','What was reported during, after and between activities?'),('Discussion for follow-up','Which adaptations or questions should be discussed with the person and care team?')]),
  ('Meaningful goals', 'Make participation goals clear enough to review together.', [('Starting point','Describe the activity as it is managed now, including assistance and environment.'),('Agreed goal','What change would matter to the person, and in what setting?'),('How to review','Which observation or chosen outcome measure will help review progress?'),('Review conversation','Record the review date, progress described and priorities that changed.')]),
  ('Session preparation', 'Connect the session to the person’s priorities and confirmed plan.', [('Agreed session aim','Which part of the participation goal will this visit address?'),('Activities and setup','What activities, equipment, setting and assistance are planned?'),('Adaptations to discuss','What flexibility is needed around energy, access, treatment appointments or preferences?'),('Response to revisit','What should be followed up at the next contact?')]),
  ('Team communication', 'Keep questions, agreed responsibilities and follow-up in one place.', [('Question or update','What needs to be clarified or communicated?'),('Person and team involved','Who needs input, and through what agreed communication route?'),('Agreed action','What was agreed, who will do it and by when?'),('Follow-up record','What reply or action remains outstanding?')]),
  ('Practice learning', 'Turn a question from practice into a specific learning action.', [('Practice question','What do you want to understand better about oncology rehabilitation?'),('Resource or discussion','Record the source, course, supervision discussion or team learning.'),('Relevance and limits','How does this relate to your setting, and what remains uncertain?'),('Action and review','What will you discuss or change in your professional practice, and when will you revisit it?')]),
 ],
 'pelvic': [
  ('Consultation preferences','Prepare a respectful and collaborative consultation.', [('Priorities','What does the person most want help with?'),('Preferences and boundaries','Which communication, comfort or accessibility preferences need to be respected?'),('Consent discussion','What explanations, choices and consent conversations need to be documented in the clinical system?'),('Questions for supervision','What do you need to clarify within your training and role?')]),
  ('Symptoms and routines','Connect the discussion to everyday participation.', [('Daily context','Which routines or activities bring up concerns?'),('Patterns described','What patterns does the person describe in their own words?'),('Impact','How are work, sleep, exercise, caregiving or other meaningful roles affected?'),('Questions to explore','What remains unclear or needs another professional’s input?')]),
  ('Agreed goals','Define the activity and the change that matters.', [('Starting point','Describe the relevant activity now.'),('Person’s goal','Record the agreed participation goal in plain language.'),('Review method','How will the person and clinician review change?'),('Review date','When will this goal be discussed again?')]),
  ('Session preparation','Prepare activities within the agreed plan.', [('Visit aim','Which goal is being addressed?'),('Education and activities','What explanations or activities have been agreed?'),('Practical adjustments','What setup, privacy, access or communication adjustments are needed?'),('Response and follow-up','What will be reviewed after the session?')]),
  ('Referral and coordination','Organize questions and shared follow-up.', [('Reason for contact','What needs clarification or another professional’s input?'),('Discussion with the person','What has been explained and agreed about communication?'),('Responsibility','Who is responsible for each next action?'),('Follow-up','Record the response or date to revisit.')]),
  ('Training and reflection','Connect continuing education with your actual scope.', [('Learning question','What skill or topic needs further learning?'),('Training record','Record the course, provider, date and relevant supervision.'),('Practice reflection','What did the learning change in your understanding?'),('Next learning action','What will you discuss, practise or review next?')]),
 ],
 'sports': [
  ('Athlete and sport','Understand participation beyond the injury label.', [('Sport demands','Record the sport, position, level and typical activity demands.'),('Current participation','What is the athlete doing now in training, competition and daily life?'),('Priorities','What matters most to the athlete at this stage?'),('Context','What access, schedule, equipment or team factors affect planning?')]),
  ('Training exposure','Keep a useful record of what was actually done.', [('Session','Record the date, activity and relevant training context.'),('Exposure','Record the agreed amount, duration or other measure used by the team.'),('Response','What did the athlete report during and after the activity?'),('Next discussion','What should be discussed before the next exposure?')]),
  ('Functional goals','Make the next stage specific and reviewable.', [('Starting point','Describe the relevant task or activity now.'),('Goal','What functional change is being targeted?'),('Evidence to review','Which chosen measures and observations will inform discussion?'),('Review','Record the date, findings and the agreed next goal.')]),
  ('Session design','Connect clinic work to the athlete’s demands.', [('Session aim','Which task or goal is this session working toward?'),('Activities','Record the planned exercise or activity within the agreed care plan.'),('Setup','What space, equipment and coaching cues are needed?'),('Response','Record what was adapted and what should be revisited.')]),
  ('Return-to-sport conversation','Record a coordinated discussion, not an automatic clearance.', [('Participation stage','What level of participation is being discussed?'),('Inputs','What athlete feedback, measures and team input are available?'),('Responsibilities','Who makes which decisions within the team’s roles?'),('Agreed plan','Record the decision, communication and review date.')]),
  ('Professional development','Build a record of learning from sport practice.', [('Question','What would you like to understand better?'),('Evidence and learning','Record the resource, supervision or course.'),('Application','How is it relevant to this sport and setting?'),('Review action','What will you test in your professional learning and revisit?')]),
 ],
 'paediatric': [
  ('Family priorities','Start with the activities that matter at home, school and play.', [('Child’s interests','What does the child enjoy and choose to do?'),('Family priorities','Which activities or routines does the family want to make easier?'),('Current participation','What can the child do now and with what support?'),('Shared focus','Which priority has been agreed for the next visit?')]),
  ('Play activity design','Prepare adaptable play rather than a fixed list of exercises.', [('Activity idea','Describe the game or meaningful task.'),('Purpose','Which agreed functional goal does it support?'),('Setup and adaptations','Record equipment, space, assistance and easier or harder variations.'),('What to observe','What participation or response will help guide the next discussion?')]),
  ('Visit planner','Give the session a clear beginning, focus and follow-up.', [('Welcome and choice','How will you include the child’s preferences?'),('Visit focus','Which activity or goal will guide the visit?'),('Activities and support','What setup, assistance and caregiver involvement are planned?'),('Debrief','What worked, what changed and what will be revisited?')]),
  ('Goal review','Review a real-life activity in its usual setting.', [('Starting point','Describe the activity, setting and assistance.'),('Agreed goal','What change would matter to the child and family?'),('Review information','Which observations or chosen measure will be reviewed?'),('Family feedback','What has changed in the routine, and what matters next?')]),
  ('Home and school collaboration','Keep shared plans practical.', [('Shared message','How will the goal be explained in plain language?'),('Routine and access','What time, space, equipment or support is available?'),('Roles','What has each person agreed to do?'),('Follow-up conversation','When and how will the plan be reviewed together?')]),
  ('Activity bank and learning','Keep ideas organized by their purpose.', [('Activity to keep','Record a play idea that was useful.'),('Adaptation','How could it be changed for another setting or interest?'),('Learning question','What needs discussion, evidence review or supervision?'),('Professional action','What will you learn or review next?')]),
 ],
}
# Additional tracks retain specialty-specific worksheet aims rather than generic repeated boxes.
TRACK_PAGES = {
 'general': [
 ('Participation profile','Meaningful roles|Current activity|Available support|Shared priority'),
 ('Visit preparation','Agreed functional goal|Session activities|Equipment and setup|Response to review'),
 ('Activity review','Task attempted|Context and assistance|Person’s feedback|Question for follow-up'),
 ('Goal review','Starting point|Agreed goal|Chosen review measure|Progress discussion'),
 ('Care coordination','Question to clarify|Team input|Agreed responsibilities|Review date'),
 ('Learning record','Practice question|Evidence or training|Relevance to this setting|Next learning action')],
 'neuro': [
 ('Mobility and participation','Meaningful daily task|Current assistance|Environment|Person’s priorities'),
 ('Task practice planner','Task goal|Setup and cues|Assistance and equipment|Response to revisit'),
 ('Carryover record','Activity practised|Setting outside the session|Support available|Feedback at review'),
 ('Functional review','Starting task performance|Chosen measure|Review findings|Agreed participation goal'),
 ('Team and caregiver discussion','Shared goal|Information to clarify|Agreed roles|Follow-up contact'),
 ('Neuro practice learning','Clinical reasoning question|Resource or supervision|Relevance to the population|Action to review')],
 'older-adults': [
 ('Daily routines','Activities that matter|Current independence|Help available|Shared priority'),
 ('Mobility and access','Task and setting|Equipment currently used|Environmental barriers|Questions for the team'),
 ('Visit planner','Functional aim|Agreed activities|Communication and access|Response to revisit'),
 ('Independence review','Starting activity|Person’s goal|Review information|Person and family feedback'),
 ('Support coordination','Who is involved|Question to clarify|Agreed responsibilities|Review timing'),
 ('Practice reflection','Decision to reflect on|What supported participation|Learning need|Professional next action')],
 'msk': [
 ('Function profile','Meaningful activity|Current difficulty|Work or daily demands|Person’s priority'),
 ('Movement and task context','Task to understand|Relevant setting|Person’s description|Question to clarify'),
 ('Session planner','Agreed aim|Planned activities|Equipment and access|Response to review'),
 ('Activity response','Activity performed|Amount and context|Feedback during and after|Follow-up discussion'),
 ('Goal review','Starting point|Agreed functional goal|Chosen measure|Progress and next priority'),
 ('Learning and communication','Practice question|Evidence or supervision|Team input|Action to revisit')],
 'custom': [
 ('Practice focus','Name your specialty|Population and setting|Professional role|Purpose of this journal'),
 ('Participation priorities','Meaningful activity|Starting point|Person’s priority|Available support'),
 ('Visit planner','Agreed aim|Planned activities|Setup and adaptations|Response to review'),
 ('Review worksheet','Activity or goal|Chosen measure|Progress discussion|Review date'),
 ('Collaboration record','Question or update|People involved|Agreed responsibilities|Follow-up'),
 ('Professional learning','Learning question|Resource or course|Relevance and limits|Next action')],
 'vestibular': [
 ('Symptoms in context','Person’s description|Activities and settings|Daily impact|Questions to clarify'),
 ('Mobility and confidence','Meaningful mobility task|Current support|Environment|Participation goal'),
 ('Visit preparation','Confirmed visit aim|Activities within the care plan|Setup and access|Response to review'),
 ('Activity response','Activity and context|Feedback during activity|Feedback afterward|Question for follow-up'),
 ('Coordination and review','Question for the team|Information available|Agreed responsibilities|Review date'),
 ('Vestibular practice learning','Learning need|Training or supervision|Relevance to your role|Professional next action')],
 'cardiorespiratory': [
 ('Activity priorities','Meaningful daily activity|Current participation|Person’s priorities|Care context to confirm'),
 ('Tolerance record','Activity and setting|Amount or duration recorded|Person’s reported response|Follow-up question'),
 ('Visit preparation','Agreed functional aim|Plan confirmed with the team|Equipment and assistance|Response to review'),
 ('Functional goal review','Starting activity|Agreed goal|Chosen measure|Review discussion'),
 ('Interdisciplinary contact','Question or update|Relevant team input|Agreed actions|Next contact'),
 ('Professional development','Practice question|Evidence or training|Relevance and limits|Review action')],
 'hand': [
 ('Hand function priorities','Activities that matter|Current difficulty|Work and home context|Shared priority'),
 ('Task analysis','Task and objects used|Environment|Assistance or adaptations|Person’s feedback'),
 ('Visit planner','Agreed functional aim|Activities within the plan|Equipment and setup|Response to review'),
 ('Function review','Starting performance|Person’s goal|Chosen review method|Progress discussion'),
 ('Coordination record','Question for the team|Information available|Agreed responsibility|Follow-up'),
 ('Hand therapy learning','Training question|Course or supervision|Application within your role|Next learning action')],
 'persistent-pain': [
 ('Meaningful activities','Roles and activities valued|Current participation|Person’s priorities|Support available'),
 ('Patterns and context','Activity and setting|Pattern described|Factors the person notices|Question to explore'),
 ('Participation planner','Agreed activity aim|Practical plan|Flexibility and access|Review conversation'),
 ('Activity response record','Activity attempted|Context and amount|Person’s feedback|What to discuss next'),
 ('Goal and collaboration review','Shared participation goal|Review information|Team input|Agreed next review'),
 ('Learning and reflection','Reasoning question|Evidence or supervision|How understanding changed|Professional action')],
 'occupational': [
 ('Work role profile','Role and work tasks|Typical demands|Person’s work priorities|Employer context to clarify'),
 ('Task and workplace context','Specific work task|Physical and environmental context|Available supports|Questions for coordination'),
 ('Work participation goals','Starting participation|Person’s goal|Information to review|Review date'),
 ('Activity and response','Task or simulation|Amount and context|Person’s feedback|Discussion before progression'),
 ('Return-to-work coordination','People involved|Information sharing agreed|Responsibilities|Follow-up conversation'),
 ('Occupational practice learning','Practice question|Resource or training|Relevance to this workplace|Learning action')],
 'community': [
 ('Home and community goals','Meaningful routine|Current participation|Person’s priorities|Support network'),
 ('Setting and access','Activity location|Access barriers described|Equipment and assistance|Questions to clarify'),
 ('Home visit preparation','Agreed aim|Activities and setup|Communication and access|Response to review'),
 ('Participation review','Starting activity|Agreed goal|Review observation|Person and caregiver feedback'),
 ('Community coordination','Services or people involved|Question or update|Agreed responsibilities|Next contact'),
 ('Practice learning','Situation to reflect on|What supported access|Evidence or supervision need|Action to revisit')],
}
DETAILS = {
 'Meaningful': 'Describe the activity in the person’s own context, rather than naming only an impairment.',
 'Agreed': 'Record what was discussed and agreed, including who is involved.',
 'Current': 'Describe the starting point and the setting in which it occurs.',
 'Response': 'Record reported responses and the question to revisit at the next contact.',
 'Review': 'Record the date, information considered and what the discussion changed.',
 'Learning': 'Record a specific question to explore through evidence, training or supervision.',
}

def worksheets(track):
    if track in WORKSHEETS:
        return [{'title':title, 'intro':intro, 'fields':[{'label':label,'prompt':prompt} for label,prompt in fields]} for title,intro,fields in WORKSHEETS[track]]
    name = EDITIONS[track][0]
    return [{'title':title, 'intro':f'{name} · {title.lower()}. Adapt this worksheet to your professional setting.',
             'fields':[{'label':label, 'prompt':next((v for k,v in DETAILS.items() if label.startswith(k)), f'Record the relevant details for {label.lower()} in this {name.lower()} worksheet.')} for label in fields.split('|')]}
            for title,fields in TRACK_PAGES[track]]
