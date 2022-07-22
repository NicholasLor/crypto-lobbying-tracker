from doctest import master
from dotenv import load_dotenv
import json
import requests
import csv
from requests.auth import HTTPBasicAuth
import pandas as pd
import re
import numpy as np
import os

pd.options.display.multi_sparse = False


# https://lda.senate.gov/api/redoc/v1/#operation/listFilings
# https://github.com/NicholasLor/bill-tracker
# https://lobbyingdisclosure.house.gov/ldaguidance.pdf

def configure():
    load_dotenv()

def formatFiling(filing_dict):

    """
    Get lobbying report details from filing dict object

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


def runQuery(inputQuery,runType):
    """
    Runs query on Senate Lobbying API with specified input sting

    runType:
        0- initial query
        1- next page query
    """
 
    # format query
    if runType == 0:
        formattedQuery = 'https://lda.senate.gov/api/v1/filings/?filing_specific_lobbying_issues={}'.format(inputQuery)
    else:
        formattedQuery = inputQuery

    # get json response
    response = requests.get(formattedQuery,headers={'Authorization':'Token '+os.getenv('senate_lobby_api')}).text
    response_info = json.loads(response)

    return response_info

def listFilings(lobbying_issue):
    """
    Docstring stub.

    """
    
    # run intial query
    response_info = runQuery(lobbying_issue,0)

    # get number of filings matching query
    num_filings = int(response_info['count'])

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
        
        

    # if there is another page, repeat
    while response_info['next'] is not None:

        # add filing to master header df
        for i in range(len(response_info['results'])):
            header_df,lobbying_df, bills_df = formatFiling(response_info['results'][i])
            master_header_df = pd.concat([master_header_df,header_df])
            master_lobbying_df = pd.concat([master_lobbying_df,lobbying_df])
            master_bills_df = pd.concat([master_bills_df,bills_df])

        # get next page 
        response_info = runQuery(response_info['next'],1)

    # add inflow type, set index and remove duplicates on master df
    master_header_df = master_header_df.set_index('filing_uuid')
    master_header_df = master_header_df[~master_header_df.index.duplicated()]
    master_header_df[['income','expenses']] = master_header_df[['income','expenses']].fillna(0)
    master_header_df['income'] = master_header_df['income'].astype(str).astype(float)
    master_header_df['expenses'] = master_header_df['expenses'].astype(str).astype(float)
    master_header_df['inflow_value'] = master_header_df['income'] + master_header_df['expenses']
    master_header_df['inflow_type'] = ['income' if x == 0 else 'expenses' for x in master_header_df['expenses']]

    # set indices on other dfs
    master_bills_df = master_bills_df.set_index(['filing_uuid','Related Bills'])
    master_lobbying_df = master_lobbying_df.set_index(['filing_uuid','general_issue_code'])

    #remove duplicates on other dfs
    master_bills_df = master_bills_df[~master_bills_df.index.duplicated()]
    master_lobbying_df = master_lobbying_df[~master_lobbying_df.index.duplicated()]

    # unsparsify indicies
    master_lobbying_df = master_lobbying_df.reset_index().set_index('filing_uuid')
    master_bills_df = master_bills_df.reset_index().set_index('filing_uuid')

    # for i in range(len(response_info['results'])):
    #     header_df,lobbying_df, bills_df = formatFiling(response_info['results'][i])
    #     master_header_df = pd.concat([master_header_df,header_df])
    #     master_lobbying_df = pd.concat([master_lobbying_df,lobbying_df])
    #     master_bills_df = pd.concat([master_bills_df,bills_df])

    # master_lobbying_df.drop_duplicates()
    # master_bills_df.drop_duplicates()

    # print master header_df
    with pd.ExcelWriter('test.xlsx'.format(lobbying_issue),
                        engine='xlsxwriter',
                        engine_kwargs={'options': {'strings_to_numbers': True}}) as writer:
        master_header_df.to_excel(writer,sheet_name="filing")
        master_lobbying_df.to_excel(writer,sheet_name="lobbying detail")
        master_bills_df.to_excel(writer,sheet_name="bill detail")



    # master_header_df.to_excel('{}.xlsx'.format(lobbying_issue))
    # master_lobbying_df.to_excel("{}_lobbying_detail.xlsx".format(lobbying_issue))
    # master_bills_df.to_excel("{}_bill_detail.xlsx".format(lobbying_issue))


def main():
    configure()
    search_string = "'cryptocurrency' OR 'cryptocurrencies' OR 'digital assets' OR 'blockchain' OR 'digital currencies' OR 'digital currency' OR 'digital token' OR 'digital tokens' OR 'digital assets' OR 'digital asset' OR 'digital asset securities' OR 'digital asset security' OR 'stablecoin' OR 'stablecoins' OR 'distributed ledger' OR 'virtual currency' OR 'virtual currencies' OR 'distributed ledgers'"
    listFilings(search_string)

main()
