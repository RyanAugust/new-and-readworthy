import requests
import sqlite3
from lxml import etree
import settings
import datetime

class inbound_local(object):
    def __init__(self, db_location=settings.db_location):
        self.db_location = db_location
        
    def _connect_to_db(self):
        """Returns connection to package sqlite db, which holds all source urls 
        as well as articles which have been previously uplaoded to Instapaper by the application"""
        con = sqlite3.connect(self.db_location)
        return con
    
    def _gather_sources(self):
        """Gathers active sources from the package db which will be referenced
        by the application when seeking newly published articles"""
        source_query = """SELECT name, connect_point, type FROM sources WHERE status=1;"""
        con = self._connect_to_db()
        c = con.cursor()
        
        source_dict = {}
        for row in c.execute(source_query):
            name, connect_point, _type = row
            if _type in source_dict.keys():
                source_dict[_type].append((name,connect_point))
            else:
                source_dict[_type] = [(name,connect_point)]
        con.commit()
        con.close()
        return source_dict

    def _rss_gather(self, source_name, rss_feed_link):
        """Pull all articles given a rss feed link
        Details that are passed back will mirror those required for insertion into the articles table
        (name, source, connect_point, publish_time)"""
        tree = etree.fromstring(requests.get(rss_feed_link).text)
        articles = tree.findall('.//item')

        articles_details = []
        status = 0
        _type = 'RSS'
        for article in articles:
            articles_details.append((article.find('title').text, source_name,
                                     article.find('link').text, article.find('pubDate').text))
        return articles_details

    def _store_article_details(self):
        """First checks that there are articles waiting to be written into the local db
        then connects and inserts each article into the `articles` table"""
        
        assert len(self.collected_articles) > 0, "No articles collected."
        
        con = self._connect_to_db()
        c = con.cursor()
        insert_query = """INSERT INTO articles (name, source, connect_point, publish_time, insert_time, uploaded)
        VALUES(?,?,?,?,?,?)"""
        uploaded = False
        insert_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:00')
        
        article_insert = []
        for article in self.collected_articles:
            name, source, connect_point, publish_time = article
            article_insert.append((name, source, connect_point, publish_time, insert_time, uploaded))
        print(article_insert)
        c.executemany(insert_query, article_insert)
        con.commit()
        con.close()
        return 0
                        
    def check_sources(self):
        """Return the sources that are currently stored within the local database"""
        source_dict = self._gather_sources()
        article_details = []
        if 'RSS' in source_dict.keys():
            for source in source_dict['RSS']:
                source_name, rss_feed_link = source
                article_details += self._rss_gather(source_name=source_name,
                                                        rss_feed_link=rss_feed_link)
                print('Sourced: {source_name}'.format(source_name=source_name))
        elif 'Medium' in source_dict.keys():
            for source in source_dict['Medium']:
                source_name, medium_link = source
                article_details += self._medium_gather(source_name=source_name,
                                                           medium_link=medium_link)
        self.collected_articles = article_details
        return 0
    
    def add_source(self, name, _type, connect_point, status):
        """Add a source to the database
        Inputs required are: 
        `name` for the source, which is what the source will be called across the db
        `_type` of page that's being referenced which tells the module how to parse stories
        `connect_point` the link to the page where the source is hosting
        `status` Boolean which designates if articles should be gathered from this source going forward
        """
        con = sqlite3.connect(self.db_location)
        c = con.cursor()
        insert_query = """INSERT INTO sources (name, type, connect_point, status, insert_time)
                VALUES(?,?,?,?,?)"""
        c.execute(
                      insert_query, (name, _type, connect_point, status, 
                      datetime.datetime.now().strftime('%Y-%m-%d %H:%M:00'))
                     )
        con.commit()
        con.close()
        return 0
    def _turn_off_source(self, source_name):
        """Ability to shut off a soruce (alteres `status` in the sources table)
        required input is only the name of the source as it is listed in the database.
        Names can be checked by using .check_sources()"""
        con = sqlite3.connect(self.db_location)
        c = con.cursor()
        off_query = """UPDATE sources SET status=0 WHERE name=?"""
        c.execute(off_query, (source_name,))
        con.commit()
        con.close()
        print('{} turned off'.format(source_name))
        return 0