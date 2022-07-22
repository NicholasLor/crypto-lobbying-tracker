from enum import unique
from dotenv import load_dotenv
import json
import requests
import csv
from requests.auth import HTTPBasicAuth
import pandas as pd
import re
import os

# API ref docs
# https://lda.senate.gov/api/redoc/v1/#operation/listFilings

def configure():
    load_dotenv()


def retrieveFiling(uuid):
    """
    Get lobbying report details with uuid

    Takes:
        uuid - filling number
        output_file - name of file to output to
        type - output file type, csv or txt

    Returns:
        header_df - df of entire json response of report filing
        lobbying_df - df of lobbyng activity detail
        bills_df  - df of bills associated with filing with format "HR XXXX"

    """
    
    # format query
    formattedQuery = 'https://lda.senate.gov/api/v1/filings/{}/'.format(uuid)

    # get json response
    response = requests.get(formattedQuery,headers={'Authorization':'Token '+os.getenv('senate_lobby_api')}).text
    response_info = json.loads(response)

    # # open csv file
    # data_file = open(output_file,'a',newline='')
    # csv_writer = csv.writer(data_file)

    # define other file names
    detail_file_list = ["registrant","client","lobbying_activities","conviction_disclosures","foreign_entities","affiliated_organizations"]    
   
    # print header info to csv
    header_df = pd.json_normalize(response_info)
    header_df.to_csv("filing_header.csv")

    # print lobbying activities to separate csv with filing id
    lobbying_df = pd.json_normalize(response_info['lobbying_activities'])
    lobbying_df['filing_uuid'] = response_info['filing_uuid']
    lobbying_df.to_csv("lobbying_activity.csv")
    
    # print list of bills covered to third df

    # parse bill numbers in all rows of description field
    x = [re.findall(r'[A-Z]\.*[A-Z]*\.*\s*[0-9]{2,4}',lobbying_df.loc[i,'description']) for i in range(len(lobbying_df.index))]
    
    # eliminate duplicates
    unique_bills_list = []
    for bill_list in x:
        for bill in bill_list:
            print(bill)
            if bill not in unique_bills_list:
                unique_bills_list.append(bill)
            
    # save to data frame and add column with uuid
    bills_df = pd.DataFrame(unique_bills_list,columns=['Related Bills'])
    bills_df['filing_uuid'] = response_info['filing_uuid']
    #bills_df.to_csv("bills_covered1.csv")

    

    #print(x)

    # Legacy Code
    """

     # write headers
    headers = {key for (key, value) in response_info.items() if key not in detail_file_list}
    csv_writer.writerow(headers)

    # write header values
    headervalues = {value for (key, value) in response_info.items() if key not in detail_file_list}
    csv_writer.writerow(headervalues)

    f = open(output_file, "w")
    f.write(headers1)
    f.close()   
    
    """
    return header_df,lobbying_df, bills_df

# ------------------ Test ------------ # 
# uuid_test = '51b9d08b-ff70-43a4-b62a-30f4a2764708'
# retrieveFiling(uuid_test)


