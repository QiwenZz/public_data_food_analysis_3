# AUTOGENERATED! DO NOT EDIT! File to edit: 00_core.ipynb (unless otherwise specified).

__all__ = ['universal_key', 'load_public_data', 'filtering_usable_data',
           'prepare_baseline_and_intervention_usable_data', 'get_adherent_column', 'most_active_user',
           'convert_loggings', 'get_certain_types', 'breakfast_analysis_summary', 'breakfast_analysis_variability',
           'dinner_analysis_summary', 'dinner_analysis_variability', 'FoodParser']

# Cell
import warnings
warnings.filterwarnings('ignore')
import pandas as pd
import numpy as np
from scipy import stats
import seaborn as sns
import os
import matplotlib.pyplot as plt
import pickle
from datetime import date
from datetime import datetime
from collections import defaultdict
import nltk
nltk.download('words', quiet=True)
nltk.download('stopwords', quiet=True)
nltk.download('wordnet', quiet=True)
nltk.download('punkt', quiet=True)
from nltk.stem import WordNetLemmatizer
from nltk.corpus import stopwords, words

import re
import string
import pkg_resources

# Cell
def universal_key(in_path):
    """
    Description:\n
        This is a helper function that converts pickle and csv file into a pd dataframe.\n

    Input:\n
        - in_path : input path, csv or pickle file\n

    Output:\n
        - df : dataframe format of the in_path file.\n

    """

    if isinstance(in_path, str):
        if in_path.split('.')[-1] == 'pickle':
            # load data
            pickle_file = open(in_path, 'rb')
            df = pickle.load(pickle_file)
            print('read the pickle file successfully.')
        if in_path.split('.')[-1] == 'csv':
            df = pd.read_csv(in_path)
            print('read the csv file successfully.')
    else:
        df = in_path

    return df

# Cell
def load_public_data(in_path):
    """
    Description:\n
        Load original public data and output processed data in pickle format.\n

        Process includes:\n
        1. Dropping 'foodimage_file_name' column.\n
        2. Handling the format of time by generating a new column, 'original_logtime_notz'\n
        3. Generating the date column, 'date'\n
        4. Converting time into float number into a new column, 'local_time'\n
        5. Converting time in the 'local_time' column so that day starts at 4 am.\n
        6. Converting time to a format of HH:MM:SS, 'time'\n
        7. Generating the column 'week_from_start' that contains the week number that the participants input the food item.\n
        8. Generating 'year' column based on the input data.\n
        9. Outputing the data into a pickle format file.\n

    Input:\n
        - in_path : input path, csv file\n

    Output:\n
        - public_all: the processed dataframe\n

    Requirements:\n
        csv file must have the following columns:\n
            - foodimage_file_name\n
            - original_logtime\n
            - date\n
            - unique_code\n
    """
    public_all = universal_key(in_path).drop(columns = ['foodimage_file_name'])

    def handle_public_time(s):
        tmp_s = s.replace('p.m.', '').replace('a.m.', '')
        try:
            return pd.to_datetime(' '.join(tmp_s.split()[:2]) )
        except:
            try:
                if int(tmp_s.split()[1][:2]) > 12:
                    tmp_s = s.replace('p.m.', '').replace('a.m.', '').replace('PM', '').replace('pm', '')
                return pd.to_datetime(' '.join(tmp_s.split()[:2]) )
            except:
                return np.nan

    original_logtime_notz_lst = []
    for t in (public_all.original_logtime.values):
        original_logtime_notz_lst.append(handle_public_time(t))
    public_all['original_logtime_notz'] = original_logtime_notz_lst

    public_all = public_all.dropna().reset_index(drop = True)

    def find_date(d):
        if d.hour < 4:
            return d.date() - pd.Timedelta('1 day')
        else:
            return d.date()
    public_all['date'] = public_all['original_logtime_notz'].apply(find_date)


    # Handle the time - Time in floating point format
    public_all['local_time'] = public_all.original_logtime_notz.apply(lambda x: pd.Timedelta(x.time().isoformat()).total_seconds() /3600.).values
    day_begins_at = 4
    public_all.loc[(public_all['local_time'] < day_begins_at), 'local_time'] = 24.0 + public_all.loc[(public_all['local_time'] < day_begins_at), 'local_time']

    # Handle the time - Time in Datetime object format
    public_all['time'] = pd.DatetimeIndex(public_all.original_logtime_notz).time

    # Handle week from start
    public_start_time_dic = dict(public_all.groupby('unique_code').agg(np.min)['date'])
    def count_week_public(s):
        return (s.date - public_start_time_dic[s.unique_code]).days // 7 + 1
    public_all['week_from_start'] = public_all.apply(count_week_public, axis = 1)

    public_all['year'] = public_all.date.apply(lambda d: d.year)

    return public_all

# Cell
def filtering_usable_data(df, num_items, num_days):
    '''
    Description:\n
        This function filters the cleaned app data so the users who satisfies the criteria are left. The criteria is that the person is left if the total loggings for that person are more than num_items and at the same time, the total days for loggings are more than num_days.\n
    Input:\n
        - df (pd.DataFrame): the dataframe to be filtered\n
        - num_items (int):   number of items to be used as cut-off\n
        - num_days (int):    number of days to be used as cut-off\n
    Output:\n
        - df_usable:         a panda DataFrame with filtered rows\n
        - set_usable:        a set of unique_code to be included as "usable"\n
    Side Effects:\n
        None\n
    Requirements:\n
        df should have the following columns:\n
            - unique_code\n
            - desc_text\n
            - date\n
    Used in:\n
        Analysis pipeline\n
    '''
    print(' => filtering_usable_data()')
    print('  => using the following criteria:', num_items, 'items and', num_days, 'days logged in two weeks.')

    # Item logged
    log_item_count = df.groupby('unique_code').agg('count')[['desc_text']].rename(columns = {'desc_text': 'Total Logged'})

    # Day counts
    log_days_count = df[['unique_code', 'date']]\
        .drop_duplicates().groupby('unique_code').agg('count').rename(columns = {'date': 'Day Count'})

    item_count_passed = set(log_item_count[log_item_count['Total Logged'] >= num_items].index)
    day_count_passed = set(log_days_count[log_days_count['Day Count'] >= num_days].index)

    print('  => # of public users pass the criteria:', end = ' ')
    print(len(item_count_passed & day_count_passed))
    passed_participant_set = item_count_passed & day_count_passed
    df_usable = df.loc[df.unique_code.apply(lambda c: c in passed_participant_set)]\
        .dropna().copy().reset_index(drop = True)
    # print('  => Now returning the pd.DataFrame object with the head like the following.')
    # display(df_usable.head(5))
    return df_usable, set(df_usable.unique_code.unique())

# Cell
def prepare_baseline_and_intervention_usable_data(in_path):
    """
    Description:\n
        Filter and create baseline_expanded and intervention groups based on in_path pickle file.\n

    Input:\n
        - in_path : input path, file in pickle, csv or pandas dataframe format\n

    Return:\n
        - baseline expanded and intervention dataframes in a list format where index 0 is the baseline dataframe and 1 is the intervention dataframe.\n

    Requirements:\n
        in_path file must have the following columns:\n
            - week_from_start\n
            - unique_code\n
            - desc_text\n
            - date\n

    """


    public_all = universal_key(in_path)

    # create baseline data
    df_public_baseline = public_all.query('week_from_start <= 2')
    df_public_baseline_usable, public_baseline_usable_id_set = \
    filtering_usable_data(df_public_baseline, num_items = 40, num_days = 12)

    # create intervention data
    df_public_intervention = public_all.query('week_from_start in [13, 14]')
    df_public_intervention_usable, public_intervention_usable_id_set = \
    filtering_usable_data(df_public_intervention, num_items = 20, num_days = 8)

    # create df that contains both baseline and intervention id_set that contains data for the first two weeks
    expanded_baseline_usable_id_set = set(list(public_baseline_usable_id_set) + list(public_intervention_usable_id_set))
    df_public_basline_usable_expanded = public_all.loc[public_all.apply(lambda s: s.week_from_start <= 2 \
                                                    and s.unique_code in expanded_baseline_usable_id_set, axis = 1)]

    return [df_public_basline_usable_expanded, df_public_intervention_usable]

# Cell
def get_adherent_column(in_path):
    """
    Description:\n
        A logging is true if the there are more than 2 loggings in one day w/ more than 4hrs apart from the earliest logging and the latest logging and False otherwise.\n

    Input:\n
        - in_path : input path, file in pickle, csv or pandas dataframe format.\n

    Return:\n
        - A dataframe with a boolean column called adherence. Details on the criteria is in the description.\n

    Requirements:\n
        in_path file must have the following columns:\n
            - unique_code\n
            - local_time\n
            - date\n

    """
    def adherent(s):
        if len(s.values) >= 2 and (max(s.values) - min(s.values)) >= 4:
            return True
        else:
            return False

    df = universal_key(in_path)

    adherent_dict = dict(df.groupby(['unique_code', 'date'])['local_time'].agg(adherent))
    df['adherence'] = df.apply(lambda x: adherent_dict[(x.unique_code, x.date)], axis = 1)

    return df

# Cell
def most_active_user(in_path, food_type = ["f", "b", "m", "w"]):
    """
    Description:\n
        This function returns a dataframe reports the number of adherent logging days for each user in the in_path file. The default order is descending.\n

    Input:\n
        - in_path : input path, file in pickle, csv or pandas dataframe format.\n
        - food_type : food types to filter in a list format. Default: ["f", "b", "m", "w"]. Available food types:\n
            1. 'w' : water \n
            2. 'b' : beverage \n
            3. 'f' : food \n
            4. 'm' : medicine \n

    Return:\n
        - A dataframe contains the number of adherent logging days for each user.\n

    Requirements:\n
        in_path file must have the following columns:\n
            - food_type\n
            - unique_code\n
            - date\n

    """

    public_all = universal_key(in_path)

    # filter the dataframe so it only contains input food type

    filtered_users = public_all.query('food_type in @food_type')

    filtered_users_w_adherence = get_adherent_column(filtered_users)

    public_top_users_day_counts = pd.DataFrame(filtered_users_w_adherence.query('adherence == True')\
                            [['date', 'unique_code']].groupby('unique_code')['date'].nunique())\
                            .sort_values(by = 'date', ascending = False).rename(columns = {'date': 'day_count'})


    return public_top_users_day_counts

# Cell
def convert_loggings(in_path):
    """
    Description:\n
       This function convert all the loggings in the in_path file into a list of individual items based on the desc_text column.\n
    Input:\n
        - in_path : input path, file in pickle, csv or panda dataframe format.\n

    Return:\n
        - A dataframe contains the cleaned version of the desc_text.\n

    Requirements:\n
        in_path file must have the following columns:\n
            - food_type\n
            - desc_text\n

    """

    public_all = universal_key(in_path)

    # initialize food parser instance
    fp = FoodParser()
    fp.initialization()

    # parse food
    parsed = [fp.parse_food(i, return_sentence_tag = True) for i in public_all.desc_text.values]

    public_all_parsed = pd.DataFrame({
    'ID': public_all.unique_code,
    'food_type': public_all.food_type,
    'desc_text': public_all.desc_text,
    'cleaned': parsed
    })

    public_all_parsed['cleaned'] = public_all_parsed['cleaned'].apply(lambda x: x[0])


    return public_all_parsed

# Cell
def get_certain_types(in_path, food_type):
    """
    Description:\n
       This function filters with the expected food types and return a cleaner version of in_path file.\n
    Input:\n
        - in_path : input path, file in pickle, csv or panda dataframe format.\n
        - food_type : expected types of the loggings for filtering, in format of list. Available types:  \n
            1. 'w' : water \n
            2. 'b' : beverage \n
            3. 'f' : food \n
            4. 'm' : medicine \n

    Return:\n
        - A filtered dataframe with expected food type/types with five columns: 'unique_code','food_type', 'desc_text', 'date', 'local_time'.\n

    Requirements:\n
        in_path file must have the following columns:\n
            - food_type\n
            - desc_text\n
            - unique_code\n
            - desc_text\n
            - date\n
            - local_time\n

    """

    df = universal_key(in_path)

    if len(food_type) == 0:
        return df[['unique_code','food_type', 'desc_text', 'date', 'local_time']]

    if len(food_type) == 1:
        if food_type[0] not in ['w', 'b', 'f', 'm']:
            raise Exception("not a valid logging type")
        filtered = df[df['food_type']==food_type[0]][['unique_code','food_type', 'desc_text', 'date', 'local_time']].reset_index(drop = True)
    else:
        filtered = df[df['food_type'].isin(food_type)][['unique_code','food_type', 'desc_text', 'date', 'local_time']].reset_index(drop = True)


    return filtered


# Cell
def breakfast_analysis_summary(in_path):
    """
    Description:\n
       This function takes the adherent loggings and calculate the 5%,10%,25%,50%,75%,90%,95% quantile of breakfast time for each user.\n

    Input:\n
        - in_path : input path, file in pickle, csv or panda dataframe format.\n

    Return:\n
        - A summary table with 5%,10%,25%,50%,75%,90%,95% quantile of breakfast time for all subjects from the in_path file.\n

    Requirements:\n
        in_path file must have the following columns:\n
            - unique_code\n
            - date\n
            - local_time\n

    """

    df = universal_key(in_path)

    # leave only the adherent loggings
    df = get_adherent_column(df)
    df = df[df['adherence']==True]

    breakfast_series = df.groupby(['unique_code', 'date'])['local_time'].min().groupby('unique_code').quantile([0.05, 0.10, 0.25, 0.5, 0.75, 0.90, 0.95])
    breakfast_df = pd.DataFrame(breakfast_series)
    all_rows = []
    for index in breakfast_df.index:
        tmp_dict = dict(breakfast_series[index[0]])
        tmp_dict['id'] = index[0]
        all_rows.append(tmp_dict)
    breakfast_summary_df = pd.DataFrame(all_rows, columns = ['id', 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95])\
        .rename(columns = {0.05: '5%', 0.1: '10%', 0.25: '25%', 0.5: '50%', 0.75: '75%', 0.9: '90%', 0.95: '95%'})\
        .drop_duplicates().reset_index(drop = True)

    return breakfast_summary_df

# Cell
def breakfast_analysis_variability(in_path):
    """
    Description:\n
       This function calculates the variability by subtracting 5%,10%,25%,50%,75%,90%,95% quantile of breakfast time from the 50% breakfast time. It also make a histogram that represents the 90%-10% interval for all subjects.\n

    Input:\n
        - in_path : input path, file in pickle, csv or panda dataframe format.\n

    Return:\n
        - A dataframe that contains 5%,10%,25%,50%,75%,90%,95% quantile of breakfast time minus 50% time for each subjects from the in_path file.\n

    Requirements:\n
        in_path file must have the following columns:\n
            - unique_code\n
            - date\n
            - local_time\n
    """


    df = universal_key(in_path)

    # leave only the adherent loggings
    df = get_adherent_column(df)
    df = df[df['adherence']==True]

    breakfast_series = df.groupby(['unique_code', 'date'])['local_time'].min().groupby('unique_code').quantile([0.05, 0.10, 0.25, 0.5, 0.75, 0.90, 0.95])
    breakfast_df = pd.DataFrame(breakfast_series)
    all_rows = []
    for index in breakfast_df.index:
        tmp_dict = dict(breakfast_series[index[0]])
        tmp_dict['id'] = index[0]
        all_rows.append(tmp_dict)
    breakfast_summary_df = pd.DataFrame(all_rows, columns = ['id', 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95])\
        .rename(columns = {0.05: '5%', 0.1: '10%', 0.25: '25%', 0.5: '50%', 0.75: '75%', 0.9: '90%', 0.95: '95%'})\
        .drop_duplicates().reset_index(drop = True)
    breakfast_variability_df = breakfast_summary_df.copy()

    for col in breakfast_variability_df.columns:
        if col == 'id' or col == '50%':
            continue
        breakfast_variability_df[col] = breakfast_variability_df[col] - breakfast_variability_df['50%']
    breakfast_variability_df['50%'] = breakfast_variability_df['50%'] - breakfast_variability_df['50%']

    fig, ax = plt.subplots(1, 1, figsize = (10, 10), dpi=80)
    sns_plot = sns.distplot( breakfast_variability_df['90%'] - breakfast_variability_df['10%'] )
    ax.set(xlabel='Variation Distribution for Breakfast (90% - 10%)', ylabel='Kernel Density Estimation')

    return breakfast_variability_df

# Cell
def dinner_analysis_summary(in_path, out_path=None, export = False):
    """
    Description:\n
       This function takes the adherent loggings and calculate the 5%,10%,25%,50%,75%,90%,95% quantile of dinner time for each user.\n

    Input:\n
        - in_path : input path, file in pickle, csv or panda dataframe format.\n

    Return:\n
        - A summary table with 5%,10%,25%,50%,75%,90%,95% quantile of dinner time for all subjects from the in_path file.\n

    Requirements:\n
        in_path file must have the following columns:\n
            - unique_code\n
            - date\n
            - local_time\n
    """

    df = universal_key(in_path)

    # leave only the adherent loggings
    df = get_adherent_column(df)
    df = df[df['adherence']==True]

    dinner_series = df.groupby(['unique_code', 'date'])['local_time'].max().groupby('unique_code').quantile([0.05, 0.10, 0.25, 0.5, 0.75, 0.90, 0.95])
    dinner_df = pd.DataFrame(dinner_series)
    all_rows = []
    for index in dinner_df.index:
        tmp_dict = dict(dinner_series[index[0]])
        tmp_dict['id'] = index[0]
        all_rows.append(tmp_dict)
    dinner_summary_df = pd.DataFrame(all_rows, columns = ['id', 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95])\
        .rename(columns = {0.05: '5%', 0.1: '10%', 0.25: '25%', 0.5: '50%', 0.75: '75%', 0.9: '90%', 0.95: '95%'})\
        .drop_duplicates().reset_index(drop = True)


    return dinner_summary_df

# Cell
def dinner_analysis_variability(in_path, out_path=None, export = False):
    """
     Description:\n
       This function calculates the variability by subtracting 5%,10%,25%,50%,75%,90%,95% quantile of dinner time from the 50% dinner time. It also make a histogram that represents the 90%-10% interval for all subjects.\n

    Input:\n
        - in_path : input path, file in pickle, csv or panda dataframe format.\n

    Return:\n
        - A dataframe that contains 5%,10%,25%,50%,75%,90%,95% quantile of dinner time minus 50% time for each subjects from the in_path file.\n

    Requirements:\n
        in_path file must have the following columns:\n
            - unique_code\n
            - date\n
            - local_time\n
    """

    df = universal_key(in_path)

    # leave only the adherent loggings
    df = get_adherent_column(df)
    df = df[df['adherence']==True]

    dinner_series = df.groupby(['unique_code', 'date'])['local_time'].max().groupby('unique_code').quantile([0.05, 0.10, 0.25, 0.5, 0.75, 0.90, 0.95])
    dinner_df = pd.DataFrame(dinner_series)
    all_rows = []
    for index in dinner_df.index:
        tmp_dict = dict(dinner_series[index[0]])
        tmp_dict['id'] = index[0]
        all_rows.append(tmp_dict)
    dinner_summary_df = pd.DataFrame(all_rows, columns = ['id', 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95])\
        .rename(columns = {0.05: '5%', 0.1: '10%', 0.25: '25%', 0.5: '50%', 0.75: '75%', 0.9: '90%', 0.95: '95%'})\
        .drop_duplicates().reset_index(drop = True)
    dinner_variability_df = dinner_summary_df.copy()

    for col in dinner_variability_df.columns:
        if col == 'id' or col == '50%':
            continue
        dinner_variability_df[col] = dinner_variability_df[col] - dinner_variability_df['50%']
    dinner_variability_df['50%'] = dinner_variability_df['50%'] - dinner_variability_df['50%']

    fig, ax = plt.subplots(1, 1, figsize = (10, 10), dpi=80)
    sns_plot = sns.distplot( dinner_variability_df['90%'] - dinner_variability_df['10%'] )
    ax.set(xlabel='Variation Distribution for Dinner (90% - 10%)', ylabel='Kernel Density Estimation')

    return dinner_variability_df

# Cell
class FoodParser():
    """
    A class that reads in food loggings from the app. Used as helper function for the function convert_loggings().
    """

    def __init__(self):
        # self.__version__ = '0.1.9'
        self.wnl = WordNetLemmatizer()
        # self.spell = SpellChecker()
        return

    ################# Read in Annotations #################
    def process_parser_keys_df(self, parser_keys_df):
        parser_keys_df = parser_keys_df.query('food_type in ["f", "b", "m", "w", "modifier", "general", "stopword", "selfcare"]').reset_index(drop = True)

        # 1. all_gram_sets
        all_gram_set = []
        for i in range(1, 6):
            all_gram_set.append(set(parser_keys_df.query('gram_type == ' + str(i)).gram_key.values))

        # 2. food_type_dict
        food_type_dict = dict(zip(parser_keys_df.gram_key.values, parser_keys_df.food_type.values))

        # 3. food2tag
        def find_all_tags(s):
            tags = []
            for i in range(1, 8):
                if not isinstance(s['tag' + str(i)], str) and np.isnan(s['tag' + str(i)]):
                    continue
                tags.append(s['tag' + str(i)])
            return tags
        food2tags = dict(zip(parser_keys_df.gram_key.values, parser_keys_df.apply(find_all_tags, axis = 1)))
        return all_gram_set, food_type_dict, food2tags

    # def run_setup(self):
    #     setup_dict = {}
    #
    #     # Read parser_keys
    #     parser_keys_df = self.read_parser_keys()
    #     all_gram_set, food_type_dict, food2tags = self.process_parser_keys_df(parser_keys_df)
    #     # my_stop_words = combined_gram_set_df.query('food_type == "stopwords"').gram_key.values
    #
    #     # Read the correction history for fire-fighters
    #     # correction_dic = pickle.load(open(pkg_resources.resource_stream(__name__, "data/correction_dic.pickle"), 'rb'))
    #     correction_dic = pickle.load(pkg_resources.resource_stream(__name__, "data/correction_dic.pickle"))
    #
    #     setup_dict['all_gram_set'] = all_gram_set
    #     setup_dict['food_type_dict'] = food_type_dict
    #     setup_dict['my_stop_words'] = my_stop_words
    #     setup_dict['correction_dic'] = correction_dic
    #     return setup_dict

    def initialization(self):
        # 1. read in manually annotated file and bind it to the object
        parser_keys_df = pd.read_csv(os.getcwd()+'/data/parser_keys.csv')
        all_gram_set, food_type_dict, food2tags = self.process_parser_keys_df(parser_keys_df)
        correction_dic = pd.read_pickle(os.getcwd()+'/data/correction_dic.pickle')
        self.all_gram_set = all_gram_set
        self.food_type_dict = food_type_dict
        self.correction_dic = correction_dic
        self.tmp_correction = {}
        # setup_dict = self.run_setup()
        # self.my_stop_words = setup_dict['my_stop_words']
        # self.gram_mask = gram_mask
        # self.final_measurement = final_measurement

        # 2. Load common stop words and bind it to the object
        stop_words = stopwords.words('english')
        # Updated by Katherine August 23rd 2020
        stop_words.remove('out') # since pre work out is a valid beverage name
        stop_words.remove('no')
        stop_words.remove('not')
        self.stop_words = stop_words
        return

    ########## Pre-Processing ##########
    # Function for removing numbers
    def handle_numbers(self, text):
        clean_text = text
        clean_text = re.sub('[0-9]+\.[0-9]+', '' , clean_text)
        clean_text = re.sub('[0-9]+', '' , clean_text)
        clean_text = re.sub('\s\s+', ' ', clean_text)
        return clean_text

    # Function for removing punctuation
    def drop_punc(self, text):
        clean_text = re.sub('[%s]' % re.escape(string.punctuation), ' ', text)
        return clean_text

    # Remove normal stopwords
    def remove_stop(self, my_text):
        text_list = my_text.split()
        return ' '.join([word for word in text_list if word not in self.stop_words])

    # def remove_my_stop(self, text):
    #     text_list = text.split()
    #     return ' '.join([word for word in text_list if word not in self.my_stop_words])

    def pre_processing(self, text):
        text = text.lower()
        # return self.remove_my_stop(self.remove_stop(self.handle_numbers(self.drop_punc(text)))).strip()
        return self.remove_stop(self.handle_numbers(self.drop_punc(text))).strip()

    ########## Handle Format ##########
    def handle_front_mixing(self, sent, front_mixed_tokens):
        # print(sent)
        cleaned_tokens = []
        for t in sent.split():
            if t in front_mixed_tokens:
                number = re.findall('\d+[xX]*', t)[0]
                for t_0 in t.replace(number, number + ' ').split():
                    cleaned_tokens.append(t_0)
            else:
                cleaned_tokens.append(t)
        return ' '.join(cleaned_tokens)

    def handle_x2(self, sent, times_x_tokens):
        # print(sent)
        for t in times_x_tokens:
            sent = sent.replace(t, ' ' + t.replace(' ', '').lower() + ' ')
        return ' '.join([s for s in sent.split() if s != '']).strip()

    def clean_format(self, sent):
        return_sent = sent

        # Problem 1: 'front mixing'
        front_mixed_tokens = re.findall('\d+[^\sxX]+', sent)
        if len(front_mixed_tokens) != 0:
            return_sent = self.handle_front_mixing(return_sent, front_mixed_tokens)

        # Problem 2: 'x2', 'X2', 'X 2', 'x 2'
        times_x_tokens = re.findall('[xX]\s*?\d', return_sent)
        if len(times_x_tokens) != 0:
            return_sent = self.handle_x2(return_sent, times_x_tokens)
        return return_sent

    ########## Handle Typo ##########
    def fix_spelling(self, entry, speller_check = False):
        result = []
        for token in entry.split():
            # Check known corrections
            if token in self.correction_dic.keys():
                token_alt = self.wnl.lemmatize(self.correction_dic[token])
            else:
                if speller_check and token in self.tmp_correction.keys():
                    token_alt = self.wnl.lemmatize(self.tmp_correction[token])
                elif speller_check and token not in self.food_type_dict.keys():
                    token_alt = self.wnl.lemmatize(token)
                    # token_alt = self.wnl.lemmatize((self.spell.correction(token)))
                    self.tmp_correction[token] = token_alt
                else:
                    token_alt = self.wnl.lemmatize(token)
            result.append(token_alt)
        return ' '.join(result)

    ########### Combine all cleaning ##########
    def handle_all_cleaning(self, entry):
        cleaned = self.pre_processing(entry)
        cleaned = self.clean_format(cleaned)
        cleaned = self.fix_spelling(cleaned)
        return cleaned

    ########## Handle Gram Matching ##########
    def parse_single_gram(self, gram_length, gram_set, gram_lst, sentence_tag):
        food_lst = []
        # print(gram_length, gram_lst, sentence_tag)
        for i in range(len(gram_lst)):
            if gram_length > 1:
                curr_word = ' '.join(gram_lst[i])
            else:
                curr_word = gram_lst[i]
            # print(curr_word, len(curr_word))
            if curr_word in gram_set and sum([t != 'Unknown' for t in sentence_tag[i: i+gram_length]]) == 0:
                # Add this founded food to the food list
                # food_counter += 1
                sentence_tag[i: i+gram_length] = str(gram_length)
                # tmp_dic['food_'+ str(food_counter)] = curr_word
                food_lst.append(curr_word)
                # print('Found:', curr_word)
        return food_lst

    def parse_single_entry(self, entry, return_sentence_tag = False):
        # Pre-processing and Cleaning
        cleaned = self.handle_all_cleaning(entry)
        # print(cleaned)

        # Create tokens and n-grams
        tokens = nltk.word_tokenize(cleaned)
        bigram = list(nltk.ngrams(tokens, 2)) if len(tokens) > 1 else None
        trigram = list(nltk.ngrams(tokens, 3)) if len(tokens) > 2 else None
        quadgram = list(nltk.ngrams(tokens, 4)) if len(tokens) > 3 else None
        pentagram = list(nltk.ngrams(tokens, 5)) if len(tokens) > 4 else None
        all_gram_lst = [tokens, bigram, trigram, quadgram, pentagram]

        # Create an array of tags
        sentence_tag = np.array(['Unknown'] * len(tokens))
        # for i in range(len(sentence_tag)):
        #     if tokens[i] in self.final_measurement:
        #         sentence_tag[i] = 'MS'

        all_food = []
        food_counter = 0
        for gram_length in [5, 4, 3, 2, 1]:
            if len(tokens) < gram_length:
                continue
            tmp_food_lst = self.parse_single_gram(gram_length,
                                                self.all_gram_set[gram_length - 1],
                                                all_gram_lst[gram_length - 1],
                                                sentence_tag)
            all_food += tmp_food_lst
        # print(sentence_tag)
        if return_sentence_tag:
            return all_food, sentence_tag
        else:
            return all_food

    def parse_food(self, entry, return_sentence_tag = False):
        result = []
        unknown_tokens = []
        num_unknown = 0
        num_token = 0
        for w in entry.split(','):
            all_food, sentence_tag = self.parse_single_entry(w, return_sentence_tag)
            result += all_food
            if len(sentence_tag) > 0:
                num_unknown += sum(np.array(sentence_tag) == 'Unknown')
                num_token += len(sentence_tag)
                cleaned = nltk.word_tokenize(self.handle_all_cleaning(w))

                # Return un-catched tokens, groupped into sub-sections
                tmp_unknown = ''
                for i in range(len(sentence_tag)):
                    if sentence_tag[i] == 'Unknown':
                        # unknown_tokens.append(cleaned[i])
                        tmp_unknown += (' ' + cleaned[i])
                        if i == len(sentence_tag) - 1:
                            unknown_tokens.append(tmp_unknown)
                    elif tmp_unknown != '':
                        unknown_tokens.append(tmp_unknown)
                        tmp_unknown = ''
        # for i in range(len(result)):
        #     if result[i] in self.gram_mask.keys():
        #          result[i] = self.gram_mask[result[i]]
        if return_sentence_tag:
            return result, num_token, num_unknown, unknown_tokens
        else:
            return result

    def find_food_type(self, food):
        if food in self.food_type_dict.keys():
            return self.food_type_dict[food]
        else:
            return 'u'

    ################# DataFrame Functions #################
    def expand_entries(self, df):
        assert 'desc_text' in df.columns, '[ERROR!] Required a column of "desc_text"!!'

        all_entries = []
        for idx in range(df.shape[0]):
            curr_row = df.iloc[idx]
            logging = curr_row.desc_text
            tmp_dict = dict(curr_row)
            if ',' in logging:
                for entry in logging.split(','):
                    tmp_dict = tmp_dict.copy()
                    tmp_dict['desc_text'] = entry
                    all_entries.append(tmp_dict)
            else:
                tmp_dict['desc_text'] = logging
                all_entries.append(tmp_dict)

        return pd.DataFrame(all_entries)
