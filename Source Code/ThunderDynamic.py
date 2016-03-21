#!/usr/bin/env python
"""ThunderDynamic - Samuel's ultimate module"""
#===============================================
__author__ = 'Thai "Samuel" Doan'
__email__ = "tdoan@hawk.iit.edu"
__status__ = "Prototype"
__copyright__ = "Not yet 2015, ThunderDynamic Productions"
#===============================================
import pandas as pd
import numpy as np
from urllib2 import urlopen
import datetime as dt
import zipfile
from StringIO import StringIO
import csv
#===============================================
# Offset a number of months from a specific date:
def ema(array):
    if len(array) == 1:
        return array[0]
    else:        
        return (array[-1]-ema(array[:-1]))*(2.0/(len(array)+1))+ema(array[:-1])

def monthdelta(date, months):
    """Substract the number of given months from the given date.
    Params:
        date: td.datetime format
        months: an integer
    Output:
        the day that (moths) previous: datetime format."""
    month_day = [None, 31, 28, 31, 30, 31, 30, 30, 31, 30, 31, 30, 31]
    shifted_month = (date.month - months%12) + 12*(date.month<=months%12)
    shifted_year = date.year - (months/12) - (months%12>=date.month)
    shifted_day = (date.day*(date.day<=month_day[shifted_month]) + month_day[shifted_month]*(date.day>month_day[shifted_month])
                    + month_day[shifted_month]*(shifted_month==2)*(shifted_year%4))
    return dt.date(shifted_year, shifted_month, shifted_day)

# Get Stock price form Yahoo Finance:
def getStock(Ticker, start_date, end_date, frequency):
    """Get stock price from Yahoo Finance.
        Params:
            Ticker: a string - ticker of the stock
            start_date, end_date: (datetime.date) format
            frequency:'m' for monthly data,
                      'd' for daily data,
                      'w' for weekly data (not recommended),
                      'v' for dividend
        Output:
            pandas.DataFrame
        Note: Yahoo csv file missing one first day compare to the displayed table on the website.
            If you want that day, enter a day earlier for the start_date"""
    try:
        url = 'http://real-chart.finance.yahoo.com/table.csv?s='
        # The retrieving method is to offset the start_date & end_date by one month. Seem stupid but January becomes 0.
        df = pd.read_csv(urlopen('%s%s&a=%s&b=%s&c=%s&d=%s&e=%s&f=%s&g=%s&ignore=.csv'%(url,Ticker, start_date.month-1,\
                                        start_date.day, start_date.year, end_date.month-1, end_date.day, end_date.year, frequency)),\
                                        index_col='Date', parse_dates= True)
        data = df
        # Relabeled montly data:
        if frequency == 'm':
            data.index = data.index.map(lambda x: dt.date(x.year, x.month, 1)) # Bring the date to the first day of the month"""
        return data
    except Exception, e:
        print 'Fail to collect data :', e

# Calculating arithmetic return:
def SReturn(Ticker, start_date, end_date, frequency):
    """Get annualized stock aruthmatic return based on Yahoo Finance data.
        Params:
            Ticker: a string - ticker of the stock
            start_date, end_date: (datetime.date) format
            frequency:frequency:'m' for monthly data,
                      'd' for daily data,
                      'w' for weekly data (not recommended),
                      'v' for dividend
        Output:
            pandas.DataFrame
        Note: Yahoo monthly data delays 1 month. Output data is relabeled."""
    a_dict = {'m':dt.datetime(start_date.year, start_date.month -1, 1),\
                'd': start_date - dt.timedelta(days=1),\
                'w': start_date - dt.timedelta(days=7),\
                'v': dt.datetime(start_date.year, start_date.month - 3, 1)} # offset the start_date to get a full period of return
    data = getStock(Ticker, a_dict[frequency], end_date, frequency).ix[:,-1:] # pull data, only take the Adj_Close column
    sreturn = ((data/data.shift(-1)) - 1) # Rolling simple return
    sreturn.columns = [Ticker]
    return sreturn[:-1]

# Calculating log return:
def LReturn(Ticker, start_date, end_date, frequency):
    """Get annualized stock logarithmic return based on Yahoo Finance data.
        Params:
            Ticker: a string - ticker of the stock
            start_date, end_date: (datetime.date) format
            frequency:frequency:'m' for monthly data,
                      'd' for daily data,
                      'w' for weekly data (not recommended),
                      'v' for dividend
            pandas.DataFrame
        Note: Yahoo monthly data delays 1 month. Output data is relabeled."""
    a_dict = {'m':dt.datetime(start_date.year, start_date.month -1, 1),\
                'd': start_date - dt.timedelta(days=1),\
                'w': start_date - dt.timedelta(days=7),\
                'v': dt.datetime(start_date.year, start_date.month - 3, 1)} # offset the start_date to get a full period of return
    data = getStock(Ticker, a_dict[frequency], end_date, frequency).ix[:,-1:] # pull data, only take the Adj_Close column
    lreturn = np.log((data/data.shift(-1))) # Rolling log return
    lreturn.columns = [Ticker]
    return lreturn[:-1]

# Get Fama-French Data
def getFF():
    """Get Fama-French 3 factors data. Right now can only return monthly data."""
    try:
        url = 'http://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip'
        zip_file = zipfile.ZipFile(StringIO(urlopen(url).read()), 'r') # Retrieve the zip file, can only be read in text stream data # Unzip
        csv_file = zip_file.open(zip_file.namelist()[0])             # Extract the csv file contains data (only 1 file in the zip file)
        data = csv.reader(csv_file)                                 # Read data

        # Parse the csv file to DataFrame:
        # Create a table of lists:
        table = []
        counter = 0
        for row in data:
            if row == []:
                counter += 1
                if counter == 2:
                    break
            table.append(row)

        # Create a header row
        table = table[3:] # Remove first 3 rows
        header = table.pop(0) # Assign the first row of the new table  to be header
        header[0] = 'Date'  # Name the first column to be used as Index

        # Write the table to a DataFrame
        ff = pd.DataFrame(table, columns=header, dtype=float)
        #ff['Date'].map(lambda x: dt.date(year=int(x)/100, month=int(x)%100)) - attemp to remap index but not a viable option without days
        format = '%Y%m.0'
        ff.Date = pd.to_datetime(ff.Date, format=format)
        ff.set_index('Date', drop=True, inplace=True)
        return ff
    except Exception,e:
        print "For some reasons unable to retreive data: ", e, ". Hint: Check your internet connection."

def StockCorrel(function, a_list, start_date, end_date, freq):
    """Return correlation matrix of Log returns on the stocks in the list.
        Params:
            function: Log_return:LReturn, Simple_return:SReturn, Stock_price:getStock
            a_list: list of strings - tickers of the stocks
            start_date, end_date: (datetime.date) format
            frequency:frequency:'m' for monthly data,
                      'd' for daily data,
                      'w' for weekly data (not recommended),
                      'v' for dividend"""
    lists = []
    for ticker in a_list:
        try:
            series = function(ticker,start_date, end_date, freq).ix[:,-1:]
            lists.append(series)
        except Exception, e:
            print e, ticker
            break
    df = pd.concat(lists, axis=1, join='outer')
    table = pd.DataFrame(np.corrcoef(df, rowvar=0), index=a_list, columns=a_list)    
    return table
    