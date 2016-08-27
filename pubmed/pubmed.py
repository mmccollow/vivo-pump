#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    pubmed.py -- tools for identifying pubmed papers, retrieving citation data for pubmed papers, and loading those
    papers into VIVO
"""

import logging
import httplib

__author__ = "Michael Conlon"
__copyright__ = "Copyright (c) 2016 Michael Conlon"
__license__ = "New BSD license"
__version__ = "0.2"

# Establish logging

logger = logging.getLogger(__name__)

#   Catalyst service access

HOST = "profiles.catalyst.harvard.edu"
API_URL = "/services/GETPMIDs/default.asp"


def get_person_catalyst_pmids(uri, query_parms):
    """
    Given a person uri, collect the attributes needed to call get_pmids and return two lists:
    a list of pubs for the person found in VIVO, and a list of pubs for the person found by
    the catalyst service
    :param uri: the uri of a person in VIVO
    :return: A dictionary of two lists, the vivo_pmids and the catalyst_pmids
    """
    from pump.vivopump import vivo_query
    query = """
    SELECT ?first ?middle ?last ?email ?affiliation
    WHERE {
      <{}>
    }
    """
    query = query.format(uri)
    a = vivo_query(query, query_parms)
    first = a['results']['bindings'][0]['first']['value']
    middle = None
    last = None
    emails = None
    affiliations = None
    return get_catalyst_pmids(first, middle, last, emails, affiliations)


def get_person_vivo_pmids(uri, query_parms):
    """
    Given the uri of a person, query VIVO to get a list of the person's publications with pmids
    :param uri:
    :return: a dictionary keyed by pmid with uris of the pubs for each pmid
    """
    from pump.vivopump import vivo_query
    query = """SELECT (MAX(?paper_uri) AS ?puri) ?pmid
    WHERE {
        <{}> vivo:relatedBy ?a .
        ?a a vivo:Authorship .
        ?a vivo:relates ?paper_uri .
        ?paper_uri a bibo:AcademicArticle .
        ?paper_uri bibo:pmid ?pmid .
    }
    GROUP BY ?pmid
    """
    query = query.replace('{}', uri)
    a = vivo_query(query, query_parms)
    pmid = [x['pmid']['value'] for x in a['results']['bindings']]
    puri = [x['puri']['value'] for x in a['results']['bindings']]
    return dict(zip(pmid, puri))


def get_catalyst_pmids(first, middle, last, email, affiliation=None):
    """
    Given an author's identifiers and affiliation information, optional lists of pmids, call the catalyst service
    to retrieve PMIDS for the author and return a list of PMIDS
    :param first: author first name
    :param middle: author middle name
    :param last: author last name
    :param email: author email(s) as a list
    :param affiliation: author affiliation as a list
    :return: list of pmids identified by the catalyst service that have a high probability of being written by the
    author
    """
    from xml.dom.minidom import parseString  # tools for handling XML in python

    result = get_catalyst_pmids_xml(first, middle, last, email, affiliation)
    dom = parseString(result)  # create a document Object Model (DOM) from the Harvard Catalyst result
    return [node.childNodes[0].data for node in dom.getElementsByTagName('PMID')]  # return a list of PMID paper


def get_catalyst_pmids_xml(first, middle, last, email, affiliation=None):
    """
    Given author name parts (first, middle and last), email(s) and optional affiliation(s),
    return the PMIDs of papers that are likely to be the works of the author.  The Harvard
    Catalyst GETPMIDS service is called.
    """
    request = """
        <?xml version="1.0"?>
        <FindPMIDs>
            <Name>
                <First>{}</First>
                <Middle>{}</Middle>
                <Last>{}</Last>
                <Suffix/>
            </Name>
            <EmailList>
                {}
            </EmailList>
            <AffiliationList>
                {}
            </AffiliationList>
            <LocalDuplicateNames>1</LocalDuplicateNames>
            <RequireFirstName>false</RequireFirstName>
            <MatchThreshold>0.98</MatchThreshold>
        </FindPMIDs>"""

    if affiliation is None:
        affiliation = []
    email_string = ''.join(['<Email>' + em + '</Email>' for em in email])
    affil_string = ''.join(['<Affiliation>' + aff + '</Affiliation>' for aff in affiliation])

    request = request.format(first, middle, last, email_string, affil_string)
    webservice = httplib.HTTP(HOST)
    webservice.putrequest("POST", API_URL)
    webservice.putheader("Host", HOST)
    webservice.putheader("User-Agent", "Python post")
    webservice.putheader("Content-type", "text/xml; charset=\"UTF-8\"")
    webservice.putheader("Content-length", "%d" % len(request))
    webservice.endheaders()
    webservice.send(request)
    statuscode, statusmessage, header = webservice.getreply()
    result = webservice.getfile().read()
    logger.debug(u"Request {}\n\tStatus Code {} Message {} Header {}\n\tResult {}".format(request, statuscode,
                                                                                          statusmessage, header,
                                                                                          result))
    return result


def get_pubmed_paper(pmid):
    """
    Given a PubMed ID, return the current the paper metadata from PubMed
    """
    from Bio import Entrez
    import time
    Entrez.email = 'mconlon@ufl.edu'
    paper = {}
    grants_cited = []
    keyword_list = []

    # Get record(s) from Entrez.  Retry if Entrez does not respond

    start = 2.0
    retries = 10
    count = 0
    while True:
        try:
            handle = Entrez.efetch(db="pubmed", id=pmid, retmode="xml")
            records = Entrez.parse(handle)
            break
        except:
            count += 1
            if count > retries:
                return {}
            sleep_seconds = start**count
            print "<!-- Failed Entrez query. Count = " + str(count)+ \
                " Will sleep now for " + str(sleep_seconds)+ \
                " seconds and retry -->"
            time.sleep(sleep_seconds)  # increase the wait time with each retry

    # Find the desired attributes in the record structures returned by Entrez

    for record in records:
        print "Entrez record:", record
        article_id_list = record['PubmedData']['ArticleIdList']
        for article_id in article_id_list:
            attributes = article_id.attributes
            if 'IdType' in attributes:
                if attributes['IdType'] == 'pmc':
                    paper["pmcid"] = str(article_id)
                    paper['full_text_uri'] = "http://www.ncbi.nlm.nih.gov/pmc/articles/" + \
                        paper['pmcid'].upper()+ "/pdf"
                if attributes['IdType'] == 'mid':
                    paper["nihmsid"] = str(article_id)
                if attributes['IdType'] == 'pubmed':
                    paper["pmid"] = str(article_id)
                if attributes['IdType'] == 'doi':
                    paper["doi"] = str(article_id)
        try:
            paper['abstract'] = \
                str(record['MedlineCitation']['Article']['Abstract']['AbstractText'][0])
        except KeyError:
            pass
        try:
            paper['title'] = \
                record['MedlineCitation']['Article']['ArticleTitle']
        except KeyError:
            pass
        try:
            keywords = record['MedlineCitation']['MeshHeadingList']
            for keyword in keywords:
                keyword_list.append(str(keyword['DescriptorName']))
            paper['keyword_list'] = keyword_list
        except KeyError:
            pass
        try:
            grants = record['MedlineCitation']['Article']['GrantList']
            for grant in grants:
                grants_cited.append(grant['GrantID'])
            paper['grants_cited'] = grants_cited
        except KeyError:
            pass

    return paper
