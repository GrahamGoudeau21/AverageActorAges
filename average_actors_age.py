import sys
import re
import urllib
import requests
import json
import datetime
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt


# defaults: no printing, use default_pdf_name
def parse_call_options():
    printing = False
    default_pdf_name = 'ages_average'
    num_args = len(sys.argv)
    if num_args == 1:
        return (printing, default_pdf_name)

    if num_args == 2 or num_args == 3:
        file_name = default_pdf_name
        arg = sys.argv[1]

        if arg[0] != '-':
            raise Exception('Unknown command line argument: \'{}\''.format(arg))

        if 'n' not in arg and num_args == 3:
            raise Exception('Unexpected number of command line argumets')

        seen_hyphen = False
        for c in arg:
            if c == '-' and not seen_hyphen:
                seen_hyphen = True
                continue
            elif c == '-' and seen_hyphen:
                raise Exception('\'-\' character only allowed at beginning of arguments')

            if c == 'v':
                printing = True
            elif c == 'n':
                if num_args == 3:
                    file_name = sys.argv[2]
                if num_args == 2:
                    raise Exception('Expected filename, none found')
            else:
                raise Exception('Unrecognized argument: \'{}\''.format(c))

        return (printing, file_name)
    else:
        raise Exception('Unexpected number of command line arguments')

def get_current_movies():
    currently_playing_api = 'http://www.myapifilms.com/imdb/inTheaters'
    try:
        r = requests.get(currently_playing_api)
    except requests.exceptions.ConnectionError:
        raise Exception('Unable to fetch currently playing movies')

    if r.status_code != 200:
        raise Exception('Unable to fetch currently playing movies')

    content = json.loads(r.content)

    in_theaters = []
    for entry in content:
        for movie in entry['movies']:
            if movie['originalTitle']:
                in_theaters.append(movie['originalTitle'])
            else:
                in_theaters.append(movie['title'])

    return in_theaters

# get a url-safe version of a movie title
def get_url_safe_title(string):
    return urllib.quote_plus(string.encode('utf8'))

# get a wiki api-safe version of an actor or actress's name
def get_url_safe_actor(string):
    # replace spaces with underscores to conform to wikipedia api
    string = string.replace(' ', '_')
    return urllib.quote_plus(string.encode('utf8'))

# requires a url-safe movie title;
# requires the current year in order to avoid naming conflicts with
# movies with the same name released in previous years
def get_actor_list(title, current_year):
    # format the api url string with the title and year to search for
    title_search_api = 'http://www.omdbapi.com/?t={}&plot=short&r=json&y={}'
    try:
        r = requests.get(title_search_api.format(title, current_year))
    except requests.exceptions.ConnectionError:
        return []

    if r.status_code != 200:
        return []

    content = json.loads(r.content)

    # try searching for movies the previous year too
    if 'Error' in content:
        r = requests.get(title_search_api.format(title, current_year - 1))
        if r.status_code != 200:
            return []

        content = json.loads(r.content)

        # if still an error, then the movie cannot be found
        if 'Error' in content:
            return []

    actors_string = content['Actors']
    actors_list = actors_string.split(',')
    # strip any leading whitespace from actor names
    for index, actor in enumerate(actors_list):
        if actor[0] == ' ':
            actors_list[index] = actor[1:]

    return actors_list

def create_graph(movie_age_map, pdf_name):
    graph_titles = movie_age_map.keys()
    graph_ages = [movie_age_map[title] for title in graph_titles]
    y_pos = xrange(len(graph_titles))

    plt.barh(y_pos, graph_ages, align='center', alpha=0.4)
    plt.yticks(y_pos, graph_titles)
    plt.xlabel('Average ages')
    plt.title('Average ages of the casts of currently playing movies')
    plt.tick_params(labelsize='small')
    plt.autoscale()
    plt.tight_layout()
    plt.savefig(pdf_name + '.pdf')

def get_average_cast_age(do_print, index, title, movie_age_map, actor_age_map):
    if do_print:
        print 'Gathering actor/actress ages for \'{}\' - '.format(title),
        print str(index + 1) + ' / ' + str(len(currently_playing_titles))

    ages = []
    actor_list = get_actor_list(get_url_safe_title(title), datetime.datetime.now().year)

    for actor in actor_list:
        safe_actor = get_url_safe_actor(actor)

        # if seen this actor already, use the cached value
        if safe_actor in actor_age_map:
            ages.append(actor_age_map[safe_actor])
        else:
            # may return None if the search failed
            age = get_actor_age(safe_actor)

            # only consider ages we actually found
            if age is not None:
                ages.append(age)
                actor_age_map[safe_actor] = age

    if len(ages) > 0:
        movie_age_map[title] = (sum(ages) * 1.0) / len(ages)


# requires url-safe actor name
def get_actor_age(actor):
    # format api url string with the actor's name
    actor_search_api = 'http://en.wikipedia.org/w/api.php?action=query&prop=revisions&rvprop=content&format=json&titles={}&rvsection=0'
    try:
        r = requests.get(actor_search_api.format(actor))
    except requests.exceptions.ConnectionError:
        return None

    if r.status_code != 200:
        return None

    content = json.loads(r.content)
    pages = content['query']['pages']

    # expect only one page
    page_number = pages.keys()[0]
    if 'missing' in pages[page_number]:
        # actor not on wikipedia or name different
        return None

    # parse the birth date of an actor or actress from the wikipedia infobox
    infobox = pages[page_number]['revisions'][0]['*']

    birth_date_regex = r'\| birth_date\s*=\s*{{.*?\|(\d+).*}}'
    search_obj = re.search(birth_date_regex, infobox)
    if search_obj:
        return datetime.datetime.now().year - int(search_obj.group(1))
    else:
        return None

if __name__ == '__main__':
    do_print, pdf_name = parse_call_options()

    if do_print:
        print 'Gathering currently playing movies...'

    currently_playing_titles = get_current_movies()
    movie_age_map = {}

    # cache actor names we have seen already
    actor_age_map = {}

    for index, title in enumerate(currently_playing_titles):
        get_average_cast_age(do_print, index, title, movie_age_map, actor_age_map)

    if do_print:
        print 'Generating PDF of the results...'
    create_graph(movie_age_map, pdf_name)
