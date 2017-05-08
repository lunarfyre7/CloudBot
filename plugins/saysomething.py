import inflect, os, json, re
import random as r
from cloudbot import hook
#todo: use pycorpora instead 
wordtree = {}
@hook.on_start()
def load(bot):
    global wordtree
    with open(os.path.join(bot.data_dir, 'wordtree.json')) as f:
        wordtree = json.load(f)

@hook.command(autohelp=False)
def saysomething(text, action):
    p = inflect.engine()
    sentence = r.choice(wordtree['sentences'])
    verb = r.choice(wordtree['verbs'])
    verb2 = r.choice(wordtree['verbs'])
    noun = r.choice(wordtree['nouns'])
    noun2 = r.choice(wordtree['nouns'])
    adv = r.choice(wordtree['adv'])
    adv2 = r.choice(wordtree['adv'])
    adj = r.choice(wordtree['adj'])
    adj2 = r.choice(wordtree['adj'])
    me = re.compile('^/me ')
    if me.match(sentence):
        sentence = me.sub('',sentence)
        action(p.inflect(sentence.format(verb=verb, noun=noun, adj=adj, adv=adv,verb2=verb2, noun2=noun2, adj2=adj2, adv2=adv2)))
    else:
        return p.inflect(sentence.format(verb=verb, noun=noun, adj=adj, adv=adv,verb2=verb2, noun2=noun2, adj2=adj2, adv2=adv2))
