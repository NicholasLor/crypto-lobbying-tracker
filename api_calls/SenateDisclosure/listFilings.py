
from doctest import master
from io import StringIO
from tkinter import X
from tkinter.messagebox import NO
from dotenv import load_dotenv, find_dotenv
import json
import requests
import csv
from requests.auth import HTTPBasicAuth
import pandas as pd
import re
import numpy as np
import os
from line_profiler import LineProfiler
from concurrent.futures import ProcessPoolExecutor, as_completed
from requests_futures.sessions import FuturesSession
import math
import psycopg2 as pg2
import sys
import csvkit
from sqlalchemy import create_engine
from pathlib import Path

# set options
pd.options.display.multi_sparse = False

#create Concurrent session 
session = FuturesSession(max_workers=50)

# API ref docs
# https://lda.senate.gov/api/redoc/v1/#operation/listFilings
# https://lobbyingdisclosure.house.gov/ldaguidance.pdf

# find .env file and load
BASEDIR = os.path.abspath(Path(__file__).parents[2])
ENV_PATH = os.path.join(BASEDIR, '.env')
load_dotenv(ENV_PATH)

API_KEY = os.getenv('senate_lobby_api')
POSTGRES_PASSWORD = os.getenv('postgres_password')
POSTGRES_USER = os.getenv('postgres_user')
POSTGRES_DB_NAME = os.getenv('postgres_db_name')

def formatFiling(filing_dict):

    """
    Gets lobbying report details from filing dict object

    Takes:
        filing_dict - dictionary of individual filing

    Returns:
        header_df - df of entire json response of report filing
        lobbying_df - df of lobbyng activity detail
        bills_df  - df of bills associated with filing with format "HR XXXX"

    """
    
    # print header info to csv
    header_df = pd.json_normalize(filing_dict)
    #header_df.to_csv("filing_header.csv")

    # print lobbying activities to separate csv with filing id
    lobbying_df = pd.json_normalize(filing_dict['lobbying_activities'])
    lobbying_df['filing_uuid'] = filing_dict['filing_uuid']
    # lobbying_df.to_csv("lobbying_activity.csv")
    
    # print list of bills covered to third df

    # parse bill numbers in all rows of description field
    x = [re.findall(r'[A-Z]\.*[A-Z]*\.*\s*[0-9]{2,4}',lobbying_df.loc[i,'description']) for i in range(len(lobbying_df.index))]


    # eliminate duplicates
    unique_bills_list = []
    for bill_list in x:
        for bill in bill_list:
            #print(bill)
            if bill not in unique_bills_list:
                bill_stripped = bill.replace(".","").replace(" ","").replace("R","B")
                unique_bills_list.append(bill_stripped)
            
    # save to data frame and add column with uuid
    bills_df = pd.DataFrame(unique_bills_list,columns=['Related Bills'])
    bills_df['filing_uuid'] = filing_dict['filing_uuid']
    #bills_df.to_csv("bills_covered1.csv")

    return header_df,lobbying_df, bills_df

def getRequest(url):
    """Gets JSON formatted response from url

    Args:
        url (string): string of url to be processed

    Returns:
        Dict: JSON object of url response
    """

    response = requests.get(url,stream=True)

    filingdict = response.json()
    # print("getresult type: "+type(filingdict))
    # print(filingdict['results'][0])

    return filingdict

def runQuery(inputQuery,runType):
    """
    Runs query on Senate Lobbying API with specified input sting

    runType:
        0- initial query
        1- next page query
    """
 
    # 0 - initial query, to get next pointer
    if runType == 0:
        formattedQuery = 'https://lda.senate.gov/api/v1/filings/?filing_specific_lobbying_issues={}'.format(inputQuery)
    else:
        formattedQuery = inputQuery

    # create requests session
    session = requests.Session()
    
    # get json response
    response = session.get(formattedQuery,headers={'Authorization':'Token '+API_KEY})
    response_info = response.json()

    return response_info

def listFilings(lobbying_issue):
    """
    Prints desired search string of Senate Lobbying database to excel file. 

    Takes:
        lobbying_issue - string to search Senate Lobbying database with

    Calls:
        runQuery()
        formatFiling()
        
    """
    
    # run intial query
    response_info = runQuery(lobbying_issue,0)

    # get number of filings and pages matching query
    num_filings = int(response_info['count'])
    num_pages = math.floor(num_filings/25)+1

    # get list of urls to query
    urls = ["https://lda.senate.gov/api/v1/filings/?filing_specific_lobbying_issues={}&page={}".format(lobbying_issue,i+1) for i in range(num_pages)]

    # print header names
    master_header_df = pd.DataFrame(columns = response_info['results'][0].keys())

    # initialize empty dfs
    master_lobbying_df = pd.DataFrame()
    master_bills_df = pd.DataFrame()

    # TO-DO:

        # link legiscan and SenateDisclosure data via bill names
            # only allow HR and S bills (not 2022, COVID19, etc.)
            # Strip out '.' in 'H.R. 3020' with no spaces
            # replace r with b
            # reference filing year
            

        # modify search query to add all crypto-related keywords
        # differentiate between pure and allied crypto lobbying companies
            # how to do this automatically?
            # lobbyist counts by stakeholder type

    # make parallel API calls and append to result_list
    result_list = []
    with ProcessPoolExecutor() as executor:

        for url, b in zip(urls, executor.map(getRequest,urls)):
            
            result_list.append(b)

    # for every api call
    for result in result_list:

        # for every row in every api call
        for row in result['results']:
            header_df,lobbying_df, bills_df = formatFiling(row)
            
            # append to master df
            master_header_df = pd.concat([master_header_df,header_df])
            master_lobbying_df = pd.concat([master_lobbying_df,lobbying_df])
            master_bills_df = pd.concat([master_bills_df,bills_df])

    # add inflow type, set index and remove duplicates on master df
    master_header_df = master_header_df.set_index('filing_uuid')
    master_header_df = master_header_df[~master_header_df.index.duplicated()]
    master_header_df[['income','expenses']] = master_header_df[['income','expenses']].fillna(0)
    master_header_df['income'] = master_header_df['income'].astype(str).astype(float)
    master_header_df['expenses'] = master_header_df['expenses'].astype(str).astype(float)

    # add inflow values
    master_header_df['inflow_value'] = master_header_df['income'] + master_header_df['expenses']
    master_header_df['inflow_type'] = ['income' if x == 0 else 'expenses' for x in master_header_df['expenses']]

    # add crypto company flag (maybe do in SQL?)

    # add in-house flag column
    # master_header_df['lobbying_type'] = [1 if master_header_df['client.name'] == master_header_df['registrant.name'] else 0 in master_header_df['filing_uuid']]

    # add merged company name column

    # set indices on other dfs
    master_bills_df = master_bills_df.set_index(['filing_uuid','Related Bills'])
    master_lobbying_df = master_lobbying_df.set_index(['filing_uuid','general_issue_code'])

    #remove duplicates on other dfs
    master_bills_df = master_bills_df[~master_bills_df.index.duplicated()]
    master_lobbying_df = master_lobbying_df[~master_lobbying_df.index.duplicated()]

    # unsparsify indicies
    master_lobbying_df = master_lobbying_df.reset_index().set_index('filing_uuid')
    master_bills_df = master_bills_df.reset_index().set_index('filing_uuid')

    master_header_df.drop(['lobbying_activities','conviction_disclosures','foreign_entities','affiliated_organizations'],axis=1,inplace=True)
    master_lobbying_df.drop(['lobbyists','government_entities'],axis=1,inplace=True)

    engine_string = 'postgresql://{}:{}@localhost:5432/{}'.format(POSTGRES_USER,POSTGRES_PASSWORD,POSTGRES_DB_NAME)
    engine = create_engine(engine_string)

    # print master header_df
    # with pd.ExcelWriter('query_aug15.xlsx',
    #                     engine='xlsxwriter',
    #                     engine_kwargs={'options': {'strings_to_numbers': True}}) as writer:
    #     master_header_df.to_excel(writer,sheet_name="filing")
    #     master_lobbying_df.to_excel(writer,sheet_name="lobbying detail")
    #     master_bills_df.to_excel(writer,sheet_name="bill detail")

    master_bills_df.to_sql('bill_detail',engine)
    master_lobbying_df.to_sql('filing_issue_detail',engine)
    master_header_df.to_sql('filing',engine)

def xlsxtocsv(filename):

    read_file = pd.read_excel("{}".format(filename)+".xlsx")

    read_file.to_csv("{}.csv".format(filename),index=None,header=True)

def df_to_sql(df,table_name):

    try:
        engine_string = 'postgresql://{}:{}@localhost:5432/{}'.format(POSTGRES_USER,POSTGRES_PASSWORD,POSTGRES_DB_NAME)
        engine = create_engine(engine_string)
        df.to_sql(table_name,engine)
    except (Exception, pg2.DatabaseError) as error:
        print("Error: %s" % error)
        return 1
    print("import to {} successful".format(table_name))

def main():
    
    # set search string
    search_string = "'cryptocurrency' OR 'cryptocurrencies' OR 'digital assets' OR 'blockchain' OR 'digital currencies' OR 'digital currency' OR 'digital token' OR 'digital tokens' OR 'digital assets' OR 'digital asset' OR 'digital asset securities' OR 'digital asset security' OR 'stablecoin' OR 'stablecoins' OR 'distributed ledger' OR 'virtual currency' OR 'virtual currencies' OR 'distributed ledgers'"

    # create lp test
    lp = LineProfiler()

    # # set up line_profiler test for listFilings
    lp_wrapper = lp(listFilings)
    lp_wrapper(search_string)
    lp.print_stats()

    # df = pd.read_csv('query_aug15.csv')
    # df_to_sql(df,'test_table')
    # listFilings(search_string)


if __name__ == '__main__':
    main()
