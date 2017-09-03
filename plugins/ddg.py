import ddg3
from cloudbot import hook

@hook.command
def ddg(text):
	q = ddg3.query(text)

	t = q.type
	if t == 'answer': 
		return q.results[0].text
	elif t == 'disambiguation': 
		return q.related[0].text,
	elif t == 'nothing': 
		return q.answer.text
	else:
		return "something's wrong"
