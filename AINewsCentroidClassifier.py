"""
AINewsCentroidClassifier aims to use Rocchio/Centroid-based classification[1] 
to train and predict 19 AI news categories. 

The classification task used to be performed by AINewsTopic.py, but it is a 
 rather simply method.

The training data is 289 manually scrutinized articles for 19 categories.
However, it is very easy to add new articles by simply put them into the
training data directory and re-train the centroid classifier.

[1] Eui-Hong Han, George Karypis, Centroid-Based Document Classification:
Analysis & Experimental Results

Date: Dec.22th, 2010
Author: Liang Dong
"""

import os
import sys
import math
import random
import operator
from subprocess import *
import time
from datetime import date, datetime, timedelta

from AINewsDB import AINewsDB
from AINewsTextProcessor import AINewsTextProcessor
from AINewsTools import loadfile2, savefile, savepickle, loadpickle, loadfile
from AINewsConfig import config, paths


class AINewsCentroidClassifier:
    def __init__(self):
        '''
        Initialization of centroid classifier for 19 AI-topic 
        '''
        period = int(config['ainews.period'])
        self.begindate = date.today() - timedelta(days = period)

        self.txtpro = AINewsTextProcessor()
        self.db = AINewsDB()
        self.corpus_count = (self.db.selectone('select count(*) from cat_corpus'))[0]
        self.cache_urls = {}

        self.wordlist = {}
        self.wordids = {}

        self.categories =["AIOverview","Agents", "Applications", \
                 "CognitiveScience","Education","Ethics", "Games", "History",\
                 "Interfaces","MachineLearning","NaturalLanguage","Philosophy",\
                 "Reasoning","Representation", "Robots","ScienceFiction",\
                 "Speech", "Systems","Vision"]
        
        self.tfijk = {}
        self.tfik = {}
        self.csd = {}
        for cat in self.categories:
            self.tfik[cat] = {}
            self.tfijk[cat] = {}
            self.csd[cat] = {}
        self.icsd = {}
        self.sd = {}
        self.cat_urlids = {}

        self.icsd_pow = 0.0
        self.csd_pow = 0.0
        self.sd_pow = 0.0
        
        
    ##############################
    #
    #           Train 
    #
    ##############################
    def train(self, category=None):
        '''
        Training procedures for all 19 centroids 
        It takes in 19 topics' training data from the src_dir,
        and outputs centroid of each topic into dest_dir.
        If category is not None, then only train that specific category.
        '''
        if category == None:
            print "\n****** Inserting category article word freqs ******\n"
            sql = '''select u.urlid, u.content from cat_corpus as u'''
            rows = self.db.selectall(sql)
            urlids = []
            i = 0
            for row in rows:
                print "%d/%d" % (i, len(rows))
                i += 1
                urlids.append(row[0])
                wordfreq = self.txtpro.whiteprocess(row[0], row[1])
                self.add_freq_index(wordfreq)
            self.commit_freq_index('wordlist')
                
            for category in self.categories:
                self.train_centroid(category, urlids, 'centroid')
        else:
            self.train_centroid(category)
        
    def train_centroid(self, category, corpus, model_dir):
        '''
        Train only one centroid of given category.
        Given the input training data in the src_dir, and output centroid
        saved as pickle file in the dest_dir.
        '''
        print "\n****** Training", category,"******"
        print "(1) Getting articles"
        corp = []
        for c in corpus:
            if category in c[2].split(' '):
                print c[0],
                corp.append(c)
        print
        print "(2) Making centroid"
        centroid = self.make_centroid(corp)
        print "(3) Saving centroid",
        savepickle(paths['ainews.category_data']+model_dir+'/'+category+'.pkl', centroid)
        
    def make_centroid(self, corpus):
        '''
        Build centroid of one category
        '''
        centroid = {} # will hold final centroid avg tfidf, indexed by wordid
        for c in corpus:
            data = self.get_tfidf(c[0], c[1])
            for word in data:
                centroid.setdefault(word, 0.0)
                centroid[word] += data[word]

        distsq = 0.0
        for word in centroid:
            distsq += centroid[word]*centroid[word]

        # Normalize centroid
        dist = math.sqrt(distsq)
        if dist > 1.0e-9:
            for key in centroid:
                centroid[key] /= dist
            
        return centroid
    
    
    ##############################
    #
    #           Predict 
    #
    ##############################
    def init_predict(self, model_dir = None, wordlist_table = 'wordlist'):
        '''
        Initialization prediction by loading 19 centroids from the directory.
        @param  model_dir: 19 centroid models path dir
        @type  model_dir: C{string}
        '''
        self.models = []
        if model_dir != None:
            for category in self.categories:
                file = os.path.join(model_dir, category+".pkl")
                self.models.append(loadpickle(file))
        self.dftext = {}
        self.wordids = {}
        rows = self.db.selectall('select rowid, word, dftext from %s' % wordlist_table)
        for row in rows:
            self.wordids[row[0]] = row[1]
            self.dftext[row[1]] = (row[0], row[2])
            
    def get_tfidf(self, urlid, content = None):
        """
        Helper function to retrieve the tfidf of each word based on the urlid.
        @param  urlid: target news story's urlid.
        @type  urlid: C{int}
        """
        if urlid in self.cache_urls:
            return self.cache_urls[urlid]
            
        wordids = {}
        if content == None:
            sql = '''select w.wordid, t.freq, w.dftext
                     from textwordurl as t, wordlist_eval as w
                     where urlid = %d and t.wordid = w.rowid''' % (urlid)
            rows = self.db.selectall(sql)
            for row in rows:
                words[row[0]] = (row[1], row[2])
        else:
            wordfreq = self.txtpro.whiteprocess(urlid, content)
            for word in wordfreq:
                if word in self.dftext:
                    wordids[self.dftext[word][0]] = (wordfreq[word], self.dftext[word][1])

        data = {}
        distsq = 0.0
        for wordid in wordids:
            tfidf = math.log(wordids[wordid][0] + 1, 2) * (math.log(self.corpus_count, 2) - \
                 math.log(wordids[wordid][1] + 1, 2))
            data[wordid] = tfidf
            distsq += tfidf * tfidf
        dist = math.sqrt(distsq)
        if dist > 1.0e-9:
            for key in data:
                data[key] /= dist
        self.cache_urls[urlid] = data
        return data
    
    def predict(self, urlid, content = None):
        '''
        Predict its category from the 19 centroids
        Given a urlid of news story, retrieve its saved term vector and
        compare it with 19 category's centroid. Choose the closest category
        as the news story's category/topic.
        '''
        data = self.get_tfidf(urlid, content)
        max_sim = 0
        max_i = 0
        similarities = {}
        for (i, model) in enumerate(self.models):
            cat = self.categories[i]
            sim = self.cos_sim(data, model, cat)
            similarities[cat] = sim
            if sim > max_sim:
                max_i = i
                max_sim = sim
        return (self.categories[max_i], similarities)

    def choose_category(self, urlid):
        '''
        Predict and set the article's category.
        '''
        meta = loadpickle(paths['ainews.news_data']+'meta/'+str(urlid)+'.pkl')
        text = loadpickle(paths['ainews.news_data']+'text/'+str(urlid)+'.pkl')
        wordfreq = self.txtpro.whiteprocess(urlid, text)
        (topic, topicsims) = self.predict(urlid)
        # Add topicsims to meta
        meta = (meta[0], meta[1], meta[2], meta[3], topicsims, topic)
        savepickle(paths['ainews.news_data']+'meta/'+str(urlid)+'.pkl', meta)

        print "Choosing category %s for urlid %d (%s)" % \
            (topic, urlid, meta[2])

        # Update category ('topic') in database
        sql = "update urllist set topic = '%s' where rowid = %d" % (topic, urlid)
        self.db.execute(sql)

    def get_candidates(self):
        """
        Get all news candidates during the candidate period.
        @return: a list of candidate news' urlid
        @rtype: C{list}
        """
        sql = """select rowid from urllist where pubdate >= '%s' and topic <> 'NotRelated' 
                 order by rowid asc""" % self.begindate
        rows = self.db.selectall(sql)
        urlids = [row[0] for row in rows]
        return urlids

    def categorize_all(self):
        self.init_predict(paths['ainews.category_data'] + 'centroid')
        candidate_urlids = self.get_candidates()
        for urlid in candidate_urlids:
            self.choose_category(urlid)

    def get_icsd(self, word):
        if word in self.icsd:
            return self.icsd[word]
        self.icsd[word] = 0.0
        for cat in self.categories:
            tmp = self.tfik[cat][word]
            for cat2 in self.categories:
                tmp -= (self.tfik[cat2][word] / float(len(self.categories)))
            tmp = tmp*tmp
            self.icsd[word] += tmp / float(len(self.categories))
        self.icsd[word] = math.sqrt(self.icsd[word])
        return self.icsd[word]

    def get_csd(self, cat, word):
        if cat in self.csd:
            if word in self.csd[cat]:
                return self.csd[cat][word]
        else:
            self.csd[cat] = {}

        self.csd[cat][word] = 0.0
        for urlid in self.cat_urlids[cat]:
            if word in self.tfijk[cat][urlid]:
                tmp = self.tfijk[cat][urlid][word] - self.tfik[cat][word]
            else:
                tmp = 0 - self.tfik[cat][word]
            self.csd[cat][word] += tmp*tmp / float(len(self.cat_urlids[cat]))
        self.csd[cat][word] = math.sqrt(self.csd[cat][word])
        return self.csd[cat][word]

    def get_sd(self, word):
        if word in self.sd:
            return self.sd[word]

        sub = 0.0
        for cat in self.categories:
            for urlid in self.tfijk[cat]:
                if word in self.tfijk[cat][urlid]:
                    sub += float(self.tfijk[cat][urlid][word]) / self.cat_totals
        self.sd[word] = 0.0
        for cat in self.categories:
            for urlid in self.tfijk[cat]:
                if word in self.tfijk[cat][urlid]:
                    tmp = self.tfijk[cat][urlid][word] - sub
                else:
                    tmp = 0 - sub
                self.sd[word] += tmp*tmp / self.cat_totals
        self.sd[word] = math.sqrt(self.sd[word])
        return self.sd[word]

    def cos_sim(self, data, centroid, category = None):
        '''
        A helper function to compute the cos simliarity between
        news story and centroid.
        @param  data: target news story tfidf vector.
        @type  data: C{dict}
        @param centroid: centroid tfidf vector.
        @type  centroid: C{dict}
        '''
        sim = 0.0
        for key in data:
            if key in centroid:
                word = self.wordids[key]
                d = data[key]
                c = centroid[key]
                tdf = math.pow(self.get_icsd(word), self.icsd_pow) * \
                        math.pow(self.get_sd(word), self.sd_pow)
                if category != None:
                        tdf *= math.pow(self.get_csd(category, word), self.csd_pow)
                sim += c*d*tdf
        return sim

    def add_freq_index(self, wordfreq, urlid, categories = []):
        for cat in categories:
            self.tfijk[cat][urlid] = {}
        for word in wordfreq:
            self.wordlist.setdefault(word, 0)
            self.wordlist[word] += 1

            for cat in categories:
                self.tfijk[cat][urlid].setdefault(word, 0)
                self.tfijk[cat][urlid][word] += wordfreq[word]

            for cat in self.categories:
                self.tfik[cat].setdefault(word, 0)
            for cat in categories:
                self.tfik[cat][word] += wordfreq[word]

    def commit_freq_index(self, table):
        # calculate tfik
        for cat in self.categories:
            for word in self.tfik[cat]:
                if len(self.cat_urlids[cat]) > 0:
                    self.tfik[cat][word] /= float(len(self.cat_urlids[cat]))

        self.cat_totals = 0.0
        for cat in self.categories:
            self.cat_totals += float(len(self.cat_urlids[cat]))

        self.icsd = {}
        self.csd = {}
        self.sd = {}

        for word in self.wordlist:
            rowid = self.db.execute("insert into "+table+" (word, dftext) values(%s, %s)", \
                        (word, self.wordlist[word]))
            self.wordids[rowid] = word
        self.wordlist = {}




    ##############################
    #
    #           Evaluate
    #
    ##############################

    def evaluate(self):
        '''
        Train on a portion of the corpus, and predict the rest;
        evaluate performance. Various parameters are evaluated.
        @param model_dir: temporary directory to store centroids
        @type model_dir: C{string}
        '''
        random.seed()
        results = {}
        iteration = 0
        iterations = 4 * 3 * 5 * 5 * 5
        for it in range(0, 4):
            for i in range(5, 10, 2):
                pct = i/10.0
                print "Selecting random %d%% of corpus." % (pct * 100)
                rows = list(self.db.selectall("""select c.urlid, c.content,
                    group_concat(cc.category separator ' ')
                    from cat_corpus as c, cat_corpus_cats as cc
                    where c.urlid = cc.urlid group by c.urlid"""))
                random.shuffle(rows)
                random.shuffle(rows)
                offset = int(len(rows)*pct)
                self.cat_urlids = {}
                train_corpus = []

                # filter out training articles that have no whitelist terms
                for c in rows[0:offset]:
                    wordfreq = self.txtpro.whiteprocess(c[0], c[1])
                    if wordfreq.N() > 0:
                        train_corpus.append(c)
                self.corpus_count = len(train_corpus)

                # filter out predict articles that have no whitelist terms
                # (these will be ignored in crawling)
                predict_corpus = []
                # always predict 10%
                for c in rows[offset:offset+int(len(rows)*0.1)]:
                    wordfreq = self.txtpro.whiteprocess(c[0], c[1])
                    if wordfreq.N() > 0:
                        predict_corpus.append(c)
    
                self.db.execute("delete from wordlist_eval")
                self.db.execute("alter table wordlist_eval auto_increment = 0")
                self.wordids = {}
                self.cache_urls = {}

                self.tfijk = {}
                self.tfik = {}
                for cat in self.categories:
                    self.tfik[cat] = {}
                    self.tfijk[cat] = {}
                for cat in self.categories:
                    self.cat_urlids[cat] = []
                for c in train_corpus:
                    for cat in c[2].split(' '):
                        self.cat_urlids[cat].append(c[0])

                for c in train_corpus:
                    sys.stdout.write('.')
                    sys.stdout.flush()
                    wordfreq = self.txtpro.whiteprocess(c[0], c[1])
                    self.add_freq_index(wordfreq, c[0], c[2].split(' '))
                self.commit_freq_index('wordlist_eval')
                print
    
                # init_predict here to establish self.dftext
                self.init_predict(paths['ainews.category_data']+'centroid_eval/',
                        'wordlist_eval')
                for category in self.categories:
                    self.train_centroid(category, train_corpus, 'centroid_eval')
                print
                
                # init_predict here to establish newly trained models
                self.init_predict(paths['ainews.category_data']+'centroid_eval/',
                        'wordlist_eval')
                for icsd_pow in range(0, 5):
                    for csd_pow in range(0, 5):
                        for sd_pow in range(0, 5):
                            self.icsd_pow = 1.0 - icsd_pow * 0.5
                            self.csd_pow = 1.0 - csd_pow * 0.5
                            self.sd_pow = 1.0 - sd_pow * 0.5
                            count_matched = 0
                            iteration += 1
                            for c in predict_corpus:
                                (topic, topicsims) = self.predict(c[0], c[1])
                                if topic in c[2].split(' '):
                                    sys.stdout.write('+')
                                    count_matched += 1
                                else:
                                    sys.stdout.write('.')
                                sys.stdout.flush()
                            print
                            result = 100.0*float(count_matched) / \
                                        float(len(predict_corpus))
                            rkey = (i, self.icsd_pow, self.csd_pow, self.sd_pow)
                            results.setdefault(rkey, [])
                            results[rkey].append(result)
                            print ("%d/%d - Matched (%d%%, icsd=%.2f, " +
                                "csd=%.2f, sd=%.2f): %d/%d = %f%%") % \
                                (iteration, iterations, 10*i, \
                                    self.icsd_pow, self.csd_pow, self.sd_pow,
                                    count_matched, len(predict_corpus), result)
                            sys.stdout.flush()

        print
        print "Summary:"
        for (i, icsd_pow, csd_pow, sd_pow) in sorted(results.keys()):
            mean, std = meanstdv(results[(i, icsd_pow, csd_pow, sd_pow)])
            print ("%d%%, icsd=%.2f, csd=%.2f, sd=%.2f matched " +
                "avg %f%% (std dev %f%%)") % \
                (10*i, icsd_pow, csd_pow, sd_pow, mean, std)
            print results[(i, icsd_pow, csd_pow, sd_pow)]
            print

        print "icsd:"
        for (word,val) in (sorted(self.icsd.iteritems(),
                key=operator.itemgetter(1), reverse=True))[0:10]:
            print "%s: %.2f" % (word, val),
        print
        print "csd:"
        for cat in self.csd:
            print cat
            for (word,val) in (sorted(self.csd[cat].iteritems(),
                    key=operator.itemgetter(1), reverse=True))[0:10]:
                print "%s: %.2f" % (word, val),
            print
            print
        print
        print "sd:"
        for (word,val) in (sorted(self.sd.iteritems(),
                key=operator.itemgetter(1), reverse=True))[0:10]:
            print "%s: %.2f" % (word, val),
        print


"""
Calculate mean and standard deviation of data x[]:
    mean = {\sum_i x_i \over n}
    std = sqrt(\sum_i (x_i - mean)^2 \over n-1)
"""
def meanstdv(x):
    from math import sqrt
    n, mean, std = len(x), 0, 0
    for a in x:
        mean = mean + a
    mean = mean / float(n)
    for a in x:
        std = std + (a - mean)**2
    std = sqrt(std / float(n-1))
    return mean, std

if __name__ == "__main__":
    start = datetime.now()
    
    cat = AINewsCentroidClassifier()

    if len(sys.argv) < 2:
        print "Provide 'train' or 'evaluate'"
        sys.exit()
    
    if sys.argv[1] == "train":
        cat.train()
    elif sys.argv[1] == "evaluate":
        cat.evaluate()
        
    print "\n\n"
    print datetime.now() - start   
       
        
     
