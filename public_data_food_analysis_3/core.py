# AUTOGENERATED! DO NOT EDIT! File to edit: 00_core.ipynb (unless otherwise specified).

__all__ = ['load_public_data', 'prepare_baseline_and_intervention_usable_data', 'adherent', 'most_active_user',
           'convert_loggings']

# Cell
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

# Cell
def load_public_data(in_path, out_path = 'data/public.pickle'):
    """
    Load public data and output processed data in pickle format.\n

    Process include:\n
    1. Dropping 'foodimage_file_name' column.\n
    2. Handling the format of time by generating a new column, 'original_logtime_notz'\n
    3. Generating the date column, 'date'\n
    4. Converting time into float number into a new column, 'local_time'\n
    5. Converting time in the 'local_time' column so that day starts at 4 am.\n
    6. Converting time to a format of HH:MM:SS, 'time'\n
    7. Generating the column 'week_from_start' that contains the week number that the participants input the food item.\n
    8. Generating 'year' column based on the input data.\n
    9. Outputing the data into a pickle format file.\n

    \n
    @param in_path : input path\n
    @param out_path: output path\n
    @return: nothing is returned.
    """
    public_all = pd.read_csv(in_path).drop(columns = ['foodimage_file_name'])

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

    public_all_pickle_file = open(out_path, 'wb')
    pickle.dump(public_all, public_all_pickle_file)
    print('data is saved at {}'.format(out_path))
    public_all_pickle_file.close()

# Cell
def prepare_baseline_and_intervention_usable_data(in_path,
                                                  baseline_expanded_out_path='data/public_basline_usable_expanded.pickle',
                                                 intervention_out_path = 'data/public_intervention_usable.pickle'):
    """
    Filter and create baseline_expanded and intervention groups based on in_path pickle file.
    @param in_path : input path, file in pickle format\n
    @param out_path: output path\n
    @return: nothing is returned.
    """
    public_all_pickle_file = open(in_path, 'rb')
    public_all = pickle.load(public_all_pickle_file)

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

    # save baseline_expanded and intervention to pickle_file
    public_pickle_file = open(baseline_expanded_out_path, 'wb')
    pickle.dump(df_public_basline_usable_expanded, public_pickle_file)
    public_pickle_file.close()
    print('baseline_expanded data is saved at {}'.format(baseline_expanded_out_path))

    public_pickle_file = open(intervention_out_path, 'wb')
    pickle.dump(df_public_intervention_usable, public_pickle_file)
    public_pickle_file.close()
    print('intervention data is saved at {}'.format(intervention_out_path))

# Cell
def adherent(s):
    """
    return True if the there are more than 2 loggings in one day w/ more than 4hrs apart from each other.
    """
    if len(s.values) >= 2 and (max(s.values) - min(s.values)) >= 4:
        return True
    else:
        return False

# Cell
def most_active_user(in_path, n, user_day_counts_path = 'data/public_top_users_day_counts.csv'):
    """
    @param in_path : input path, file in pickle format\n
    @param n: number of users with most number of logging days\n
    @param user_data_counts_path: output path for top_users_day_counts in csv format\n
    @return: top_users_day_counts dataframe\n

    This function returns a dataframe in csv format that finds top n users with the most number of days that they logged.
    """
    public_all_pickle_file = open(in_path, 'rb')
    public_all = pickle.load(public_all_pickle_file)

    # filter the dataframe so it only contains food and beverage food type, then get the top n users who input the
    # most loggings in descending order
    top_users = public_all.query('food_type in ["f", "b"]')[['ID', 'unique_code']]\
    .groupby('unique_code').agg('count').sort_values(by = 'ID', ascending = False).index[:n]
    top_users = set(list(top_users))
    public_top_users = public_all.query('food_type in ["f", "b"]')\
    .loc[public_all.unique_code.apply(lambda x: x in top_users)].reset_index(drop = True)


    adherent_dict = dict(public_top_users.groupby(['unique_code', 'date'])['local_time'].agg(adherent))
    public_top_users['adherence'] = public_top_users\
    .apply(lambda x: adherent_dict[(x.unique_code, x.date)], axis = 1)

    public_top_users_day_counts = pd.DataFrame(public_top_users.query('adherence == True')\
                            [['date', 'unique_code']].groupby('unique_code')['date'].nunique())\
                            .sort_values(by = 'date', ascending = False).rename(columns = {'date': 'day_count'})

    public_top_users_day_counts.to_csv(user_day_counts_path)

    print('user day counts data is saved at {}'.format(user_day_counts_path))

    return public_top_users_day_counts


# Cell
def convert_loggings(in_path, parsed_food_path='data/public_all_parsed.csv', ascending = False):
    """
    @param in_path : input path, file in pickle format\n
    @param parsed_food_path : output path for cleaned food loggings in csv format \n
    @return: frequency count of food loggings in the descending order by default\n

    This function takes in a pickle file, convert all the loggings into individual items of food and count the frequency of all food loggings.
    """

    # load data
    public_all_pickle_file = open(in_path, 'rb')
    public_all = pickle.load(public_all_pickle_file)

    # initialize food parser instance
    fp = FoodParser()
    fp.initialization()

    # parse food
    parsed = [fp.parse_food(i, return_sentence_tag = True) for i in public_all.desc_text.values]

    print('All food is parsed!')

    public_all_parsed = pd.DataFrame({
    'ID': public_all.ID,
    'food_type': public_all.food_type,
    'desc_text': public_all.desc_text,
    'cleaned': parsed
    })

    public_all_parsed['cleaned'] = public_all_parsed['cleaned'].apply(lambda x: x[0])

    public_all_parsed.to_csv(parsed_food_path)
    print('cleaned food loggings is saved at {}'.format(parsed_food_path))

    # count food
    all_count_dict = defaultdict(lambda : 0)
    for food in public_all_parsed.cleaned.values:
        if len(food) > 0:
            for f in food:
                all_count_dict[f] += 1

    print('All food is counted!')

    all_count_dict = dict(all_count_dict)
    public_freq_count = pd.DataFrame({
        'food': list(all_count_dict.keys()),
        'count': [all_count_dict[k] for k in list(all_count_dict.keys())]
    }).sort_values(by = 'count', ascending = ascending).reset_index(drop = True)

    return public_freq_count