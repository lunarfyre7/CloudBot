from cloudbot import hook
import math
import sys
import operator as op 

def parse(string):
	return parseTokens(tokenize(string))
def tokenize(chars):
    return chars.replace('(', ' ( ').replace(')', ' ) ').split()
	
def parseTokens(tokens):
	depth = 0
	lst=[] #main list
	head = []
	while len(tokens) >0:
		token = tokens.pop(0)
		if token == '(':
			depth +=1
			head = [] #reset head 
		elif token == ')':
			depth -=1
			lst.append(head) #push head 
		else:
			head.append(atom(token))
			
	if depth > 0:
		raise("Expected )")
	elif depth < 0: 
		raise("Expected (")
	else:
		return lst
		
env = {
	'+': op.add,
	'-': op.sub,
	'*': op.mul,
	'/': op.truediv,
	'**':op.pow
}
class atom:
	def __init__(self, token):
		self.str = token
		try:
			self.val = int(token)
			self.type = int
		except ValueError:
			try:
				self.val = float(token)
				self.type = float
			except ValueError:
				self.val = token
				self.type = type(token)

def eval(code, env):
	action = False
	queue = []
	for index, l in enumerate(code):
		if type(l) == list:
			return eval(l, env)
		elif type(l) == atom:
			if index==0:
				action=env[l.val]
				assert(l.type==str)
			else:
				queue.append(l.val)
				assert(l.type==int or l.type == float)
	#process queue
	res = queue.pop(0)
	while len(queue) >0:
		res = action(res, queue.pop(0))
	return res
			
if __name__ == '__main__':	
	print(eval(parse(' '.join(sys.argv[1:])),env))

@hook.command()
def mewcalc(text):
	return eval(parse(text),env)
