__author__ = 'Thai (Samuel) Doan'
__email__ = 'tdoan@hawk.iit.edu'
__status__ = 'Prototype'
import pandas as pd
import numpy as np
import datetime as dt
from ThunderDynamic import *
import os
from Tkinter import *
import sys
#===========Current issue and future improvement:
#   (Done!)1. The calculation was entirely executed in the database (really slow speed) ---> bring the structure to variable watch algo
#   (Done!)2. Write the main structure into a callable function so we can mass produce results for abitrage number of pairs
#   (Done!)3. Universe of x00 securities pick 4 pairs with high correlations in pairs, low correlation between pairs
#   4. GUI
#   (Not Done!)5. Improve the algorithm with Kalman filter
#   (Done!)6. Portfolio management with capital control
#   (Done!)7. Create a database file for quickly access
#   (Not Done!)8. Tune the program so it can work with missing data
#===========Test script using database file===========

#=========Test Module in variables==========

#=====Call online data to an excel file:
pairs = (('cmcsk','cmcsa'),('gld','slv'), ('blv','biv'), ('%5EVIX','spy'), ('qqq','xlk'))

end_date = dt.date(2015, 11, 30)
start_date = dt.date(2008, 1, 1)
"""
data_list = []
for pair in pairs:
    for ticker in pair:
        series = getStock(ticker, start_date, end_date, 'd').ix[:,-1:]
        series.columns = [ticker]
        data_list.append(series)
table = pd.concat(data_list, axis=1, join='outer')
table.sort_index().to_excel(os.path.join(os.path.dirname(__file__), 'Pairs_Data.xlsx'))
"""
#=====Trading Method:
#Create a set of 2 signal dictionaries accordingly to the 2 situations when short term moving average > longterm moving average, and vice versal.
signal_set = [{(-10000,-3):'BUY3', (-3,-2):'BUY2', (-2,-0.5):'BUY1', (-0.01,0.01):'neutral', (0.5,2):'SELL1', (2,3):'SELL2', (3,10000):'SELL3'},\
              {(-10000,-3):'BUY3', (-3,-2):'BUY2', (-2,-1):'BUY1', (-0.01,0.01):'neutral', (1,2):'SELL1', (2,3):'SELL2', (3,10000):'SELL3'}]
capital = 1000000
try:
    path = os.path.dirname(os.path.abspath(__file__))
except NameError:  # We are the main py2exe script, not a module
    path = os.path.dirname(os.path.abspath(sys.argv[0]))

#Create method for trading: trading algorithm + accounting
def PairTrading(ticker_A, ticker_B, start_date, end_date, signal_set, capital):
    #Read data file and create a new dataframe to work on:
    try:
        root = os.path.dirname(os.path.abspath(__file__))
    except NameError:  # We are the main py2exe script, not a module
        root = os.path.dirname(os.path.abspath(sys.argv[0]))
    path = os.path.join(root, 'Pairs_Data.xlsx')
    table = pd.read_excel(path, index_col=0)
    col_list = ['A','B','Beta', 'MA_Beta', 'Spread', 'Spread_SMA', 'Spread_LMA','Spread_sig','Z','Signal','Status','Action', 'pos_A', 'pos_B', 'MtM', 'Acc']

    #global df#For testing purpose, disable when done! (call a dataframe to audit)
    df = pd.DataFrame(columns=col_list)
    df['A'] = table[ticker_A][start_date:end_date]
    df['B'] = table[ticker_B][start_date:end_date]
    correl = np.corrcoef(df.ix[:,'A':'B'], rowvar=0)[0][1]
    if correl > 0:#If positive correlation, execute long/short spread
        direction = 1
    if correl < 0:#If negative correlation, execute same direction spread
        direction = -1

    #df['A'] = getStock(pairs[0][0], start_date, end_date, 'd').ix[:,-1]
    #df['B'] = getStock(pairs[0][1], start_date, end_date, 'd').ix[:,-1]

    #Calculate Indicator:
    if r'%5EVIX' in [ticker_A, ticker_B]:
        df['Beta'] = 0.5*(df.A/df.A.shift(1))**2
    else:
        df['Beta'] = (df.A/df.B)
    df['MA_Beta'] = pd.rolling_mean(df['Beta'], 26)#26 days moving average
    df['Spread'] = df.A - df.MA_Beta*df.B
    df['Spread_SMA'] = pd.rolling_mean(df['Spread'], 5)#short moving average
    df['Spread_LMA'] = pd.rolling_mean(df['Spread'], 12)#long moving average
    df['Spread_sig'] = pd.rolling_std(df['Spread'], 12)#long std
    df['Z'] = (df['Spread']-df['Spread_LMA'])/df['Spread_sig']#Z-transform

    #Create a function to assign signal with each Z-transform:
    def signalFilter(Z, signal_dict):#if Z is in the range of a signal, say (1,2), assign the signal following the definition in dictionary, (SELL1).
        for i in signal_dict.keys():
            if Z>=i[0] and Z<i[1]:
                return signal_dict[i]

    #Specify initial input:
    status = 'neutral'
    cost = 0
    current_pos_A = 0
    current_pos_B = 0
    winners = {}
    losers = {}
    break_even = []
    account_value = capital
    MtM_account_value = capital
    status_dict = {'BUY3':3, 'BUY2':2, 'BUY1':1, 'neutral':0, 'SELL1':-1, 'SELL2':-2, 'SELL3':-3}#status is the current # of spread holding.(-1 = short one spread, 3 = long 3 spread)

    #Start assigning Signal-Status-Action:
    for i in range(1,len(df.index)):
        #Use different set of signals
        if df.Spread_SMA[i]>df.Spread_LMA[i]:
            signal_dict = signal_set[0]#if short-term MA > long-term MA, use the first set of dictionary
        else:
            signal_dict = signal_set[1]#else use the second set of dictionary
        #
        df.ix[i, 'Signal'] = signalFilter(df.Z[i], signal_dict)#Assign signals
        MtM_PL = (current_pos_A*(df.A[i]-df.A[i-1])+ current_pos_B*(df.B[i]-df.B[i-1]))#Calculate Mark-to-market everyday
        MtM_account_value += MtM_PL
        #df.ix[i, 'MtM'] = MtM_account_value#For testing purpose, disable when done!
        Signal = df.Signal[i]
        #Assign actions based on current status & signals
        if status != Signal and Signal != None:#if status and signal are different
            if status == 'neutral':
                action = Signal#if there was no position, accept the signal
            elif status[:3] == Signal[:3]:#if status and signal are in the same direction
                if int(Signal[-1])<int(status[-1]):
                    action = None#if already in higher position, ignore signal
                else:
                    action = Signal#if already in lower position, accept signal
            else:
                action = Signal#if status and signal are not in the same direction, always accept signal
        else:
            action = None#if status and signal are the same, nothing happen
        if i == (len(df.index)-1):#overdrive to unwind the trade at the end of the period
            action = 'neutral'
        #df.ix[i, 'Status'] = status#For testing purpose, disable when done!
        #df.ix[i, 'Action'] = action#For testing purpose, disable when done!

        if action != None:#if there were to be transaction
            new_price_A = df.A[i]
            new_price_B = df.B[i]
            new_Beta_traded = df.MA_Beta[i]
            #If to unwind the trade: (Go neutral or go flat before assign opposite direction trade)
            if status!='neutral'and (action=='neutral' or action[:3]!=status[:3]):
                #What everhappen unwind the trade first:
                PL_closed_trade = current_pos_A*new_price_A+current_pos_B*new_price_B-cost#Current value of the position minus the cost (pos_A & pos_B already in oposite sign)
                account_value += PL_closed_trade
                if PL_closed_trade > 0:
                    winners[df.index[i]] = PL_closed_trade#Watch profit value
                elif PL_closed_trade < 0:
                    losers[df.index[i]] = PL_closed_trade#Watch loss value
                else:
                    break_even.append(df.index[i])#Nevermind!
                current_pos_A = 0#Reset both positions
                current_pos_B = 0
                status = 'neutral'#Reset status
                cost = 0#Reset cost
                MtM_account_value = account_value#Reset Mark to market account since we're using leverage
            #If to post new position: (no initial position or execute a bigger position in the same direction)
            if status=='neutral' or (action[:3]==status[:3] and int(action[-1])>int(status[-1])):
                #Use account value, instead of Mark to market, when the trade closes they have to be the same
                new_spread = (account_value)/(new_price_A+new_Beta_traded*new_price_B)
                additional_spread = (status_dict[action]-status_dict[status])*new_spread#buy or sell a spread (use positive, negative sign for direction)
                if account_value < 0:#If already lose all the money, go straight to the McDonald door.
                    new_pos_A = 0
                    new_pos_B = 0
                else:
                    new_pos_A = current_pos_A + additional_spread#A use the same direction
                    new_pos_B = current_pos_B - direction*new_Beta_traded*additional_spread#B use the oposite postion
                #df.ix[i,'pos_A'] = new_pos_A#For testing purpose, disable when done!
                #df.ix[i,'pos_B'] = new_pos_B#For testing purpose, disable when done!
                cost += (new_price_A-direction*new_price_B*new_Beta_traded)*additional_spread
                current_pos_A = new_pos_A
                current_pos_B = new_pos_B

            status = action#Update status to the current position
        #df.ix[i, 'Acc'] = account_value#For testing purpose, disable when done!
        #Calculate performance statistics:
    try:
        win = sum(winners.values())
        lose = sum(losers.values())
        num_winners = len(winners.values())
        num_losers = len(losers.values())
        max_win = max(winners.values())
        max_lose = min(losers.values())
        aver_win = np.mean(winners.values())
        aver_lose = np.mean(losers.values())
        win_chance = num_winners*1.0/(num_winners+num_losers)
        lose_chance = num_losers*1.0/(num_winners+num_losers)
        expectedValue = aver_win*win_chance + aver_lose*lose_chance
        profit_factor = -sum(winners.values())/sum(losers.values())
    except:
        return [0,0,0,0,0,0,0,0,0,0,0,0,0]
    #print 'Pair: '+ticker_A +' - '+ ticker_B
    #print '# of Winners:' + str(num_winners)
    #print '# of Losers:' + str(num_losers)
    #print 'Max Win: ' + str(max_win)
    #print 'Max lose: ' +str(max_lose)
    #print '$ of Winners: $' +str(win)
    #print '$ of Losers: $' +str(lose)
    #print 'Net P&L: $' +str(win+lose)
    #print 'Profit Factor: ' + str(round(profit_factor,2))
    #print [aver_win, round(win_chance*100,2), aver_lose, round(lose_chance*100,2), expectedValue]
    #print 'Final Account Value: $' + str(round(account_value, 2))
    #print 'Final MtM Account Value: $' + str(round(MtM_account_value, 2))
    #print '\t'
    #All set for this: Accounting-checked, Algorithm-checked
    return [account_value, win, lose, num_winners, num_losers, max_win, max_lose, aver_win, aver_lose, win_chance,\
            lose_chance, expectedValue, profit_factor]

#Create main function to reallocate capital among pairs:
def mainFunction(pairs, start_date, end_date, signal_set, capital):
    capital_each = capital/len(pairs)
    #print capital_each#for testing only, disable when done
    capital_allocation = {}#create a dictionary of $ amount invest in each pair
    for pair in pairs:
        capital_allocation[pair] = capital_each#assign the initial money for each pair (equally)
    month_increment = 12#adjust capital every 12 months

    #i = 0#for testing only, disable when done
    performance_tracker = {}
    trading_account = {}
    end_period = start_date#dummy fill the varaible
    while end_period < end_date:#Trade until the end_date in the main function
        end_period = monthdelta(start_date, -month_increment)
        start_period = start_date - dt.timedelta(45)#Go back previously 45 days to start calculating the statistic, make sure the result will not ovelap last period trade
        #
        for pair in pairs:
            #each pair trade with the amount of capital assigned
            trade = PairTrading(pair[0], pair[1], start_period, end_period, signal_set, capital_allocation[pair])
            trading_account[pair] = trade[0]#track end of period balances
            #performance_tracker[trade['Profit Factor']] = pair#track performance each pair by profit factor
            performance_tracker[pair] = trade[-1]#track performance each pair by profit factor
        #
        #print trading_account#for testing only, disable when done
        #print sum(trading_account.values()), '\t'#for testing only, disable when done
        #print performance_tracker#for testing only, disable when done
        sorted_rank = sorted(performance_tracker.items(), key=lambda pair: pair[1])#sort pair by performance, sorted_rank is a list
        #print sorted_rank#for testing only, disable when done
        capital_allocation = trading_account
        #Reallocate capital:
        capital_allocation[sorted_rank[-1][0]] = trading_account[sorted_rank[-1][0]] + 0.2*trading_account[sorted_rank[0][0]]#Take 20% of the worst pair, put into the best pair
        capital_allocation[sorted_rank[-2][0]] = trading_account[sorted_rank[-2][0]] + 0.1*trading_account[sorted_rank[1][0]]#Take 10% of the second worst pair, put into the second best pair
        capital_allocation[sorted_rank[0][0]] = 0.8*trading_account[sorted_rank[0][0]]#Take away 20%
        capital_allocation[sorted_rank[1][0]] = 0.9*trading_account[sorted_rank[1][0]]#Take away 10%
        #print sum(capital_allocation.values()), '\t'#for testing only, disable when done
        start_date = end_period + dt.timedelta(1)
        #i+=1#for testing only, disable when done
        #if i == 3:#for testing only, disable when done
            #break
    return trading_account

#PairTrading(pairs[0][0], pairs[0][1], start_date, end_date, signal_set, capital)
#PairTrading(pairs[3][0], pairs[3][1], start_date, end_date, signal_set, capital)
#PairTrading(pairs[1][0], pairs[1][1], start_date, end_date, signal_set, capital)
#print PairTrading(pairs[2][0], pairs[2][1], start_date, end_date, signal_set, capital)
#print PairTrading(pairs[4][0], pairs[4][1], start_date, end_date, signal_set, capital)
#print mainFunction(pairs, start_date, end_date, signal_set, capital)

#=====GUI=====
class Window(Frame):
    def __init__(self, master=None):
        Frame.__init__(self, master, width=900, height=900, padx=5, pady=5)
        self.grid()
        #self.columnconfigure(
        self.inputFrame()
        self.displayFrame()
        self.warningLabel()
        
    def inputFrame(self):
        self.fstBSig = DoubleVar()
        self.sndBSig = DoubleVar()
        self.thdBSig = DoubleVar()
        self.fstSSig = DoubleVar()
        self.sndSSig = DoubleVar()
        self.thdSSig = DoubleVar()
        self.iniCap = DoubleVar()
        self.fstBSig.set(-1)
        self.sndBSig.set(-2)
        self.thdBSig.set(-3)
        self.fstSSig.set(1)
        self.sndSSig.set(2)
        self.thdSSig.set(3)
        self.iniCap.set(1000000)
        self.input_frame = LabelFrame(self, width=900, height=300, relief=GROOVE, padx=2, pady=2, text=' Input Controls')
        self.CalculateButton = Button(self.input_frame, text='Calculate', command=self.CalculateFunction, relief=GROOVE, overrelief=RAISED, width=20)
        self.Buy1 = Entry(self.input_frame, textvariable=self.fstBSig, width=10)
        self.Buy2 = Entry(self.input_frame, textvariable=self.sndBSig, width=10)
        self.Buy3 = Entry(self.input_frame, textvariable=self.thdBSig, width=10)
        self.Sell1 = Entry(self.input_frame, textvariable=self.fstSSig, width=10)
        self.Sell2 = Entry(self.input_frame, textvariable=self.sndSSig, width=10)
        self.Sell3 = Entry(self.input_frame, textvariable=self.thdSSig, width=10)
        self.Capital = Entry(self.input_frame, textvariable=self.iniCap)
        self.Sig1 = Label(self.input_frame, text='First signal', width=12)
        self.Sig2 = Label(self.input_frame, text='Second signal', width=12)
        self.Sig3 = Label(self.input_frame, text='Third signal', width=12)
        self.BuyLabel = Label(self.input_frame, text='Buy', height=2)
        self.SellLabel= Label(self.input_frame, text='Sell', height=2)
        self.capitalLabel = Label(self.input_frame, text='Initial Capital', width=25)
        self.Note = Label(self.input_frame, justify=LEFT, text="*Note: Based on the initial input, when short-term indicator exceeds long-term indicator, the program will be more aggressive. If normally we buy at -1, then we buy at -0.5, if we sell at 1, then we initiate buy at 0.5.", wraplength=600, anchor=NW, padx=5, pady=5, relief=GROOVE)
        self.startDateLabel = Label(self.input_frame, text="Start Date: 1/1/2008", justify=LEFT)
        self.endDateLabel = Label(self.input_frame, text="End Date: 11/30/2015", justify=LEFT)
        self.startDateLabel.grid(column=4, row=1)
        self.endDateLabel.grid(column=4, row=2)
        self.Buy1.grid(column=1, row=1)
        self.Buy2.grid(column=2, row=1)
        self.Buy3.grid(column=3, row=1)
        self.Sell1.grid(column=1, row=2)
        self.Sell2.grid(column=2, row=2)
        self.Sell3.grid(column=3, row=2)
        self.Sig1.grid(column=1, row=0)
        self.Sig2.grid(column=2, row=0)
        self.Sig3.grid(column=3, row=0)
        self.BuyLabel.grid(column=0, row=1)
        self.SellLabel.grid(column=0, row=2)
        self.capitalLabel.grid(column=5, row=0, columnspan=7)
        self.Capital.grid(row=1, column=5, columnspan=7)
        self.CalculateButton.grid(column=5, row=3, columnspan=7)
        self.Note.grid(column=0, columnspan=5, row=3)
        self.input_frame.grid(column=0, row=0)
        

    def displayFrame(self):
        self.displayFrame = LabelFrame(self, width=900, height=600, text='Trading results', padx=2, pady=2)
        self.Portfolio = LabelFrame(self.displayFrame, height=225, width=255, text='Portfolio', padx=2, pady=2, labelanchor=N)
        self.Pair0 = LabelFrame(self.displayFrame, height=225, width=255, text='CMCSK - CMCSA', padx=2, pady=2, labelanchor=N)
        self.Pair1 = LabelFrame(self.displayFrame, height=225, width=255, text='GLD - SLV', padx=2, pady=2, labelanchor=N)
        self.Pair2 = LabelFrame(self.displayFrame, height=225, width=255, text='BLV - BIV', padx=2, pady=2, labelanchor=N)
        self.Pair3 = LabelFrame(self.displayFrame, height=225, width=255, text='VIX - SPY', padx=2, pady=2, labelanchor=N)
        self.Pair4 = LabelFrame(self.displayFrame, height=225, width=255, text='QQQ - XLK', padx=2, pady=2, labelanchor=N)
        
        self.P1 = DoubleVar()
        self.P2 = DoubleVar()
        self.P3 = DoubleVar()
        self.P4 = DoubleVar()
        self.P5 = DoubleVar()
        self.P6 = DoubleVar()
        self.Portfolio_01 = Label(self.Portfolio, text='Initial Capital:  ')
        self.Portfolio_01.grid(column=0, row=0)
        self.Portfolio_02 = Label(self.Portfolio, text='Final Account Value:  ')
        self.Portfolio_02.grid(column=0, row=1)
        self.Portfolio_03 = Label(self.Portfolio, text='CMCSK-CMCSA:  ')
        self.Portfolio_03.grid(column=0, row=2)
        self.Portfolio_04 = Label(self.Portfolio, text='GLD-SLV:  ')
        self.Portfolio_04.grid(column=0, row=3)
        self.Portfolio_05 = Label(self.Portfolio, text='BLV-BIV:  ')
        self.Portfolio_05.grid(column=0, row=4)
        self.Portfolio_06 = Label(self.Portfolio, text='VIX-SPY:  ')
        self.Portfolio_06.grid(column=0, row=5)
        self.Portfolio_07 = Label(self.Portfolio, text='QQQ-XLK:  ')
        self.Portfolio_07.grid(column=0, row=6)
        self.P0Label = Label(self.Portfolio, textvariable=self.iniCap)
        self.P0Label.grid(column=1, row=0)
        self.P1Label = Label(self.Portfolio, textvariable=self.P1)
        self.P1Label.grid(column=1, row=1)
        self.P2Label = Label(self.Portfolio, textvariable=self.P2)
        self.P2Label.grid(column=1, row=2)
        self.P3Label = Label(self.Portfolio, textvariable=self.P3)
        self.P3Label.grid(column=1, row=3)
        self.P4Label = Label(self.Portfolio, textvariable=self.P4)
        self.P4Label.grid(column=1, row=4)
        self.P5Label = Label(self.Portfolio, textvariable=self.P5)
        self.P5Label.grid(column=1, row=5)
        self.P6Label = Label(self.Portfolio, textvariable=self.P6)
        self.P6Label.grid(column=1, row=6)

        self.P01 = DoubleVar()
        self.P02 = DoubleVar()
        self.P03 = DoubleVar()
        self.P04 = DoubleVar()
        self.P05 = DoubleVar()
        self.P06 = DoubleVar()
        self.P07 = DoubleVar()
        self.P08 = DoubleVar()
        self.Pair0_01 = Label(self.Pair0, text='Initial Capital:  ')
        self.Pair0_01.grid(column=0, row=0)
        self.Pair0_02 = Label(self.Pair0, text='Final Account Value:  ')
        self.Pair0_02.grid(column=0, row=1)
        self.Pair0_03 = Label(self.Pair0, text='Numer of Trade:  ')
        self.Pair0_03.grid(column=0, row=2)
        self.Pair0_04 = Label(self.Pair0, text='Win chance:  ')
        self.Pair0_04.grid(column=0, row=3)
        self.Pair0_05 = Label(self.Pair0, text='Maximum Win:  ')
        self.Pair0_05.grid(column=0, row=4)
        self.Pair0_06 = Label(self.Pair0, text='Maximum Loss:  ')
        self.Pair0_06.grid(column=0, row=5)
        self.Pair0_07 = Label(self.Pair0, text='Profit factor:  ')
        self.Pair0_07.grid(column=0, row=6)
        self.Pair0_08 = Label(self.Pair0, text='Expected Value (each trade):  ')
        self.Pair0_08.grid(column=0, row=7)
        self.Pair0_09 = Label(self.Pair0, text='Total P&L:  ')
        self.Pair0_09.grid(column=0, row=8)
        self.P00Label = Label(self.Pair0, textvariable=self.iniCap)
        self.P00Label.grid(column=1, row=0)
        self.P01Label = Label(self.Pair0, textvariable=self.P01)
        self.P01Label.grid(column=1, row=1)
        self.P02Label = Label(self.Pair0, textvariable=self.P02)
        self.P02Label.grid(column=1, row=2)
        self.P03Label = Label(self.Pair0, textvariable=self.P03)
        self.P03Label.grid(column=1, row=3)
        self.P04Label = Label(self.Pair0, textvariable=self.P04)
        self.P04Label.grid(column=1, row=4)
        self.P05Label = Label(self.Pair0, textvariable=self.P05)
        self.P05Label.grid(column=1, row=5)
        self.P06Label = Label(self.Pair0, textvariable=self.P06)
        self.P06Label.grid(column=1, row=6)
        self.P07Label = Label(self.Pair0, textvariable=self.P07)
        self.P07Label.grid(column=1, row=7)
        self.P08Label = Label(self.Pair0, textvariable=self.P08)
        self.P08Label.grid(column=1, row=8)

        self.P11 = DoubleVar()
        self.P12 = DoubleVar()
        self.P13 = DoubleVar()
        self.P14 = DoubleVar()
        self.P15 = DoubleVar()
        self.P16 = DoubleVar()
        self.P17 = DoubleVar()
        self.P18 = DoubleVar()
        self.Pair1_01 = Label(self.Pair1, text='Initial Capital:  ')
        self.Pair1_01.grid(column=0, row=0)
        self.Pair1_02 = Label(self.Pair1, text='Final Account Value:  ')
        self.Pair1_02.grid(column=0, row=1)
        self.Pair1_03 = Label(self.Pair1, text='Numer of Trade:  ')
        self.Pair1_03.grid(column=0, row=2)
        self.Pair1_04 = Label(self.Pair1, text='Win chance:  ')
        self.Pair1_04.grid(column=0, row=3)
        self.Pair1_05 = Label(self.Pair1, text='Maximum Win:  ')
        self.Pair1_05.grid(column=0, row=4)
        self.Pair1_06 = Label(self.Pair1, text='Maximum Loss:  ')
        self.Pair1_06.grid(column=0, row=5)
        self.Pair1_07 = Label(self.Pair1, text='Profit factor:  ')
        self.Pair1_07.grid(column=0, row=6)
        self.Pair1_08 = Label(self.Pair1, text='Expected Value (each trade):  ')
        self.Pair1_08.grid(column=0, row=7)
        self.Pair1_09 = Label(self.Pair1, text='Total P&L:  ')
        self.Pair1_09.grid(column=0, row=8)
        self.P10Label = Label(self.Pair1, textvariable=self.iniCap)
        self.P10Label.grid(column=1, row=0)
        self.P11Label = Label(self.Pair1, textvariable=self.P11)
        self.P11Label.grid(column=1, row=1)
        self.P12Label = Label(self.Pair1, textvariable=self.P12)
        self.P12Label.grid(column=1, row=2)
        self.P13Label = Label(self.Pair1, textvariable=self.P13)
        self.P13Label.grid(column=1, row=3)
        self.P14Label = Label(self.Pair1, textvariable=self.P14)
        self.P14Label.grid(column=1, row=4)
        self.P15Label = Label(self.Pair1, textvariable=self.P15)
        self.P15Label.grid(column=1, row=5)
        self.P16Label = Label(self.Pair1, textvariable=self.P16)
        self.P16Label.grid(column=1, row=6)
        self.P17Label = Label(self.Pair1, textvariable=self.P17)
        self.P17Label.grid(column=1, row=7)
        self.P18Label = Label(self.Pair1, textvariable=self.P18)
        self.P18Label.grid(column=1, row=8)

        self.P21 = DoubleVar()
        self.P22 = DoubleVar()
        self.P23 = DoubleVar()
        self.P24 = DoubleVar()
        self.P25 = DoubleVar()
        self.P26 = DoubleVar()
        self.P27 = DoubleVar()
        self.P28 = DoubleVar()
        self.Pair2_01 = Label(self.Pair2, text='Initial Capital:  ')
        self.Pair2_01.grid(column=0, row=0)
        self.Pair2_02 = Label(self.Pair2, text='Final Account Value:  ')
        self.Pair2_02.grid(column=0, row=1)
        self.Pair2_03 = Label(self.Pair2, text='Numer of Trade:  ')
        self.Pair2_03.grid(column=0, row=2)
        self.Pair2_04 = Label(self.Pair2, text='Win chance:  ')
        self.Pair2_04.grid(column=0, row=3)
        self.Pair2_05 = Label(self.Pair2, text='Maximum Win:  ')
        self.Pair2_05.grid(column=0, row=4)
        self.Pair2_06 = Label(self.Pair2, text='Maximum Loss:  ')
        self.Pair2_06.grid(column=0, row=5)
        self.Pair2_07 = Label(self.Pair2, text='Profit factor:  ')
        self.Pair2_07.grid(column=0, row=6)
        self.Pair2_08 = Label(self.Pair2, text='Expected Value (each trade):  ')
        self.Pair2_08.grid(column=0, row=7)
        self.Pair2_09 = Label(self.Pair2, text='Total P&L:  ')
        self.Pair2_09.grid(column=0, row=8)
        self.P20Label = Label(self.Pair2, textvariable=self.iniCap)
        self.P20Label.grid(column=1, row=0)
        self.P21Label = Label(self.Pair2, textvariable=self.P21)
        self.P21Label.grid(column=1, row=1)
        self.P22Label = Label(self.Pair2, textvariable=self.P22)
        self.P22Label.grid(column=1, row=2)
        self.P23Label = Label(self.Pair2, textvariable=self.P23)
        self.P23Label.grid(column=1, row=3)
        self.P24Label = Label(self.Pair2, textvariable=self.P24)
        self.P24Label.grid(column=1, row=4)
        self.P25Label = Label(self.Pair2, textvariable=self.P25)
        self.P25Label.grid(column=1, row=5)
        self.P26Label = Label(self.Pair2, textvariable=self.P26)
        self.P26Label.grid(column=1, row=6)
        self.P27Label = Label(self.Pair2, textvariable=self.P27)
        self.P27Label.grid(column=1, row=7)
        self.P28Label = Label(self.Pair2, textvariable=self.P28)
        self.P28Label.grid(column=1, row=8)

        self.P31 = DoubleVar()
        self.P32 = DoubleVar()
        self.P33 = DoubleVar()
        self.P34 = DoubleVar()
        self.P35 = DoubleVar()
        self.P36 = DoubleVar()
        self.P37 = DoubleVar()
        self.P38 = DoubleVar()
        self.Pair3_01 = Label(self.Pair3, text='Initial Capital:  ')
        self.Pair3_01.grid(column=0, row=0)
        self.Pair3_02 = Label(self.Pair3, text='Final Account Value:  ')
        self.Pair3_02.grid(column=0, row=1)
        self.Pair3_03 = Label(self.Pair3, text='Numer of Trade:  ')
        self.Pair3_03.grid(column=0, row=2)
        self.Pair3_04 = Label(self.Pair3, text='Win chance:  ')
        self.Pair3_04.grid(column=0, row=3)
        self.Pair3_05 = Label(self.Pair3, text='Maximum Win:  ')
        self.Pair3_05.grid(column=0, row=4)
        self.Pair3_06 = Label(self.Pair3, text='Maximum Loss:  ')
        self.Pair3_06.grid(column=0, row=5)
        self.Pair3_07 = Label(self.Pair3, text='Profit factor:  ')
        self.Pair3_07.grid(column=0, row=6)
        self.Pair3_08 = Label(self.Pair3, text='Expected Value (each trade):  ')
        self.Pair3_08.grid(column=0, row=7)
        self.Pair3_09 = Label(self.Pair3, text='Total P&L:  ')
        self.Pair3_09.grid(column=0, row=8)
        self.P30Label = Label(self.Pair3, textvariable=self.iniCap)
        self.P30Label.grid(column=1, row=0)
        self.P31Label = Label(self.Pair3, textvariable=self.P31)
        self.P31Label.grid(column=1, row=1)
        self.P32Label = Label(self.Pair3, textvariable=self.P32)
        self.P32Label.grid(column=1, row=2)
        self.P33Label = Label(self.Pair3, textvariable=self.P33)
        self.P33Label.grid(column=1, row=3)
        self.P34Label = Label(self.Pair3, textvariable=self.P34)
        self.P34Label.grid(column=1, row=4)
        self.P35Label = Label(self.Pair3, textvariable=self.P35)
        self.P35Label.grid(column=1, row=5)
        self.P36Label = Label(self.Pair3, textvariable=self.P36)
        self.P36Label.grid(column=1, row=6)
        self.P37Label = Label(self.Pair3, textvariable=self.P37)
        self.P37Label.grid(column=1, row=7)
        self.P38Label = Label(self.Pair3, textvariable=self.P38)
        self.P38Label.grid(column=1, row=8)

        self.P41 = DoubleVar()
        self.P42 = DoubleVar()
        self.P43 = DoubleVar()
        self.P44 = DoubleVar()
        self.P45 = DoubleVar()
        self.P46 = DoubleVar()
        self.P47 = DoubleVar()
        self.P48 = DoubleVar()
        self.Pair4_01 = Label(self.Pair4, text='Initial Capital:  ')
        self.Pair4_01.grid(column=0, row=0)
        self.Pair4_02 = Label(self.Pair4, text='Final Account Value:  ')
        self.Pair4_02.grid(column=0, row=1)
        self.Pair4_03 = Label(self.Pair4, text='Numer of Trade:  ')
        self.Pair4_03.grid(column=0, row=2)
        self.Pair4_04 = Label(self.Pair4, text='Win chance:  ')
        self.Pair4_04.grid(column=0, row=3)
        self.Pair4_05 = Label(self.Pair4, text='Maximum Win:  ')
        self.Pair4_05.grid(column=0, row=4)
        self.Pair4_06 = Label(self.Pair4, text='Maximum Loss:  ')
        self.Pair4_06.grid(column=0, row=5)
        self.Pair4_07 = Label(self.Pair4, text='Profit factor:  ')
        self.Pair4_07.grid(column=0, row=6)
        self.Pair4_08 = Label(self.Pair4, text='Expected Value (each trade):  ')
        self.Pair4_08.grid(column=0, row=7)
        self.Pair4_09 = Label(self.Pair4, text='Total P&L:  ')
        self.Pair4_09.grid(column=0, row=8)
        self.P40Label = Label(self.Pair4, textvariable=self.iniCap)
        self.P40Label.grid(column=1, row=0)
        self.P41Label = Label(self.Pair4, textvariable=self.P41)
        self.P41Label.grid(column=1, row=1)
        self.P42Label = Label(self.Pair4, textvariable=self.P42)
        self.P42Label.grid(column=1, row=2)
        self.P43Label = Label(self.Pair4, textvariable=self.P43)
        self.P43Label.grid(column=1, row=3)
        self.P44Label = Label(self.Pair4, textvariable=self.P44)
        self.P44Label.grid(column=1, row=4)
        self.P45Label = Label(self.Pair4, textvariable=self.P45)
        self.P45Label.grid(column=1, row=5)
        self.P46Label = Label(self.Pair4, textvariable=self.P46)
        self.P46Label.grid(column=1, row=6)
        self.P47Label = Label(self.Pair4, textvariable=self.P47)
        self.P47Label.grid(column=1, row=7)
        self.P48Label = Label(self.Pair4, textvariable=self.P48)
        self.P48Label.grid(column=1, row=8)




        self.displayFrame.grid(column=0, row=2)
        self.Portfolio.grid(column=0, row=0)
        self.Portfolio.grid_propagate(0)
        self.Pair0.grid(column=1, row=0)
        self.Pair0.grid_propagate(0)
        self.Pair1.grid(column=2, row=0)
        self.Pair2.grid(column=0, row=1)
        self.Pair3.grid(column=1, row=1)
        self.Pair4.grid(column=2, row=1)
        self.Pair1.grid_propagate(0)
        self.Pair2.grid_propagate(0)
        self.Pair3.grid_propagate(0)
        self.Pair4.grid_propagate(0)
    
    def CalculateFunction(self):        
        pairs = (('cmcsk','cmcsa'),('gld','slv'), ('blv','biv'), (r'%5EVIX','spy'), ('qqq','xlk'))
        end_date = dt.date(2015, 11, 30)
        start_date = dt.date(2008, 1, 1)
        signal_set = [{(-10000,self.thdBSig.get()):'BUY3', (self.thdBSig.get(),self.sndBSig.get()):'BUY2', (self.sndBSig.get(),self.fstBSig.get()+0.5):'BUY1', (-0.01,0.01):'neutral', (self.fstSSig.get()-0.5,self.sndSSig.get()):'SELL1', (self.sndSSig.get(),self.thdSSig.get()):'SELL2', (self.thdSSig.get(),10000):'SELL3'},\
                    {(-10000,self.thdBSig.get()):'BUY3', (self.thdBSig.get(),self.sndBSig.get()):'BUY2', (self.sndBSig.get(),self.fstBSig.get()):'BUY1', (-0.01,0.01):'neutral', (self.fstSSig.get(),self.sndSSig.get()):'SELL1', (self.sndSSig.get(),self.thdSSig.get()):'SELL2', (self.thdSSig.get(),10000):'SELL3'}]
        capital = self.iniCap.get()
        portfolio = mainFunction(pairs, start_date, end_date, signal_set, capital)
        pair0 = PairTrading(pairs[0][0], pairs[0][1], start_date, end_date, signal_set, capital)
        pair1 = PairTrading(pairs[1][0], pairs[1][1], start_date, end_date, signal_set, capital)
        pair2 = PairTrading(pairs[2][0], pairs[2][1], start_date, end_date, signal_set, capital)
        pair3 = PairTrading(pairs[3][0], pairs[3][1], start_date, end_date, signal_set, capital)
        pair4 = PairTrading(pairs[4][0], pairs[4][1], start_date, end_date, signal_set, capital)
        result = [portfolio, pair0, pair1, pair2, pair3, pair4]
        self.P1.set(round(sum(result[0].values()),2))
        self.P2.set(round(result[0][('cmcsk', 'cmcsa')],2))
        self.P3.set(round(result[0][('gld', 'slv')],2))
        self.P4.set(round(result[0][('blv', 'biv')],2))
        self.P5.set(round(result[0][('%5EVIX','spy')],2))
        self.P6.set(round(result[0][('qqq', 'xlk')],2))
        
        self.P01.set(round(result[1][0],2))
        self.P02.set(round(result[1][3]+result[1][4],2))
        self.P03.set(round(result[1][-4]*100,2))
        self.P04.set(round(result[1][5],2))
        self.P05.set(round(result[1][6],2))
        self.P06.set(round(result[1][-1],2))
        self.P07.set(round(result[1][-2],2))
        self.P08.set(round(result[1][0]-self.iniCap.get(),2))
        
        self.P11.set(round(result[2][0],2))
        self.P12.set(round(result[2][3]+result[2][4],2))
        self.P13.set(round(result[2][-4]*100,2))
        self.P14.set(round(result[2][5],2))
        self.P15.set(round(result[2][6],2))
        self.P16.set(round(result[2][-1],2))
        self.P17.set(round(result[2][-2],2))
        self.P18.set(round(result[2][0]-self.iniCap.get(),2))
        
        self.P21.set(round(result[3][0],2))
        self.P22.set(round(result[3][3]+result[3][4],2))
        self.P23.set(round(result[3][-4]*100,2))
        self.P24.set(round(result[3][5],2))
        self.P25.set(round(result[3][6],2))
        self.P26.set(round(result[3][-1],2))
        self.P27.set(round(result[3][-2],2))
        self.P28.set(round(result[3][0]-self.iniCap.get(),2))
        
        self.P31.set(round(result[4][0],2))
        self.P32.set(round(result[4][3]+result[4][4],2))
        self.P33.set(round(result[4][-4]*100,2))
        self.P34.set(round(result[4][5],2))
        self.P35.set(round(result[4][6],2))
        self.P36.set(round(result[4][-1],2))
        self.P37.set(round(result[4][-2],2))
        self.P38.set(round(result[4][0]-self.iniCap.get(),2))
        
        self.P41.set(round(result[5][0],2))
        self.P42.set(round(result[5][3]+result[5][4],2))
        self.P43.set(round(result[5][-4]*100,2))
        self.P44.set(round(result[5][5],2))
        self.P45.set(round(result[5][6],2))
        self.P46.set(round(result[5][-1],2))
        self.P47.set(round(result[5][-2],2))
        self.P48.set(round(result[5][0]-self.iniCap.get(),2))
    def warningLabel(self):
        self.warningLabel = Label(self, text='*Warning: The program might took more than 30 seconds to run!')
        self.warningLabel.grid(column=0, row=3)
        

#"""
def main():
    root = Window()
    root.master.title('Statistical Abitrage Trading')
    img = os.path.join(path, 'icon.ico')
    root.master.wm_iconbitmap(img)
    root.mainloop()

if __name__=="__main__":
    main()
#"""
