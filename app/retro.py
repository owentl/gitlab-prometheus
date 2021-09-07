import requests
import datetime
import re
from collections import Counter
import os
import logging

logFormatter = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(format=logFormatter, level=logging.DEBUG)
logger = logging.getLogger(__name__)


GITLAB_URL = 'https://gitlab.com/api/v4/'
GITLAB_TOKEN = os.environ.get("GL_ACCESS_TOKEN")
GITLAB_PROJECT_ID = ""

# Gitlab headers to pass when making API call
GITLAB_HEADERS = {
    'PRIVATE-TOKEN': GITLAB_TOKEN
}

# set this to false if JIRA / Gitlab is using self-signed certificate.
VERIFY_SSL_CERTIFICATE = True

PROJECT_MAP = {
    'iteratons': xxxxxx,  ## Where do the iterations live
    'config': xxxxxxx     ## Where is the config.json file
}

#This maps team calls to labels.  To expand to more teams, add more entries.
# The left key is what is called in slack and the value is the label to filter by

# fileURL = GITLAB_URL + "api/v4/projects/{}/repository/files/retro.json/raw?ref=master".format(PROJECT_MAP['config'])
LABEL_MAP = requests.get(
    GITLAB_URL + "projects/{}/repository/files/warpigs.json/raw?ref=master".format(PROJECT_MAP['config']),
    headers=GITLAB_HEADERS,
    verify=VERIFY_SSL_CERTIFICATE
).json()

gl_iterations = []

def get_all_iterations(p_id):
    gl_iterations = requests.get(
        GITLAB_URL + "groups/{}/{}".format(p_id,"iterations"),
        headers=GITLAB_HEADERS,
        verify=VERIFY_SSL_CERTIFICATE
    ).json()
    return gl_iterations

def get_issues(current_iteration_title,page):
    response = requests.get(
        GITLAB_URL + "groups/{}/issues?iteration_title={}&per_page=100&page={}".format(PROJECT_MAP['iterations'],current_iteration_title,page),
        headers=GITLAB_HEADERS,
            verify=VERIFY_SSL_CERTIFICATE
    )
    return response

def summarize_status(issues):
    label_tally = Counter()
    for issue in issues:
        for label in issue['labels']:
            if re.search('Dev GS::',label):
                label_tally[label] += 1
    return label_tally

def weight_by_assignee(issues):
    w_tally = Counter()
    timespent_tally = Counter()
    timesestimate_tally = Counter()
    count_tally = Counter()
    for issue in issues:
        for users in issue['assignees']:
            user = users['name']
            if issue['weight'] is None:
                weight = 0
            else:
                weight = issue['weight']

            if issue['time_stats']['total_time_spent'] is None:
                timespent = 0
            else:
                timespent = issue['time_stats']['total_time_spent']//3600
            if issue['time_stats']['time_estimate'] is None:
                timeestimate = 0
            else:
                timeestimate = issue['time_stats']['time_estimate']//3600

            w_tally[user] += weight
            timespent_tally[user] += timespent
            timesestimate_tally[user] += timeestimate
            count_tally[user] += 1

    for tally in w_tally:
        # logger.info("{} : {}..spent {}.. estimated {}".format(tally, w_tally[tally],timespent_tally[tally],timesestimate_tally[tally]))
        return (w_tally,timespent_tally,timesestimate_tally,count_tally)

def weight_by_team(issues):
    overall_weight = 0
    w_tally = Counter()
    label_tally = Counter()
    timespent_tally = Counter()
    timesestimate_tally = Counter()
    overall_timespent = 0
    overall_timeestimate = 0
    
    for issue in issues:
        if issue['weight'] is None:
           weight = 0
        else:
            weight = issue['weight']
        #Calculate overall weight for iteration
        overall_weight += weight
        
        if issue['time_stats']['total_time_spent'] is None:
            timespent = 0
        else:
            timespent = issue['time_stats']['total_time_spent']//3600
        if issue['time_stats']['time_estimate'] is None:
            timeestimate = 0
        else:
            timeestimate = issue['time_stats']['time_estimate']//3600
        overall_timespent += timespent
        overall_timeestimate += timeestimate
        #get a weight by label breakdown
        for label in issue['labels']:
            if re.search('Dev GS::',label):
                label_tally[label] += weight
                timesestimate_tally[label] += timeestimate
                timespent_tally[label] += timespent
        
    return (overall_weight, label_tally,overall_timeestimate,overall_timespent,timesestimate_tally,timespent_tally)

def report(label_counts,weight,timespent,timeestimate,team,l_issues,l_count):
    now = datetime.datetime.now()
    message = {
        "team": team,
        "issue_count": len(l_issues),
        "date_run": str(now),   
    }
    
    message['issues_by_status'] = [label_counts]
    message['issues_by_weight'] = [weight]
    message['timespent'] = [timespent]
    message['timestimate'] = [timeestimate]
    message['tickets_by_user'] = [l_count]

    return message

def report_summary(overall_weight, label_tally,issue_count,label_counts,team,timeestimate,timespent,timesestimate_tally,timespent_tally):
    now = datetime.datetime.now()
    message = {
        "team": team,
        "issue_count": issue_count,
        "overall_weight": overall_weight,
        "time_spent": timespent,
        "time_estimate": timeestimate,
        "date_run": str(now),   
    }
   
    message['issues_by_status'] = label_counts
    message['issues_by_weight'] = label_tally
    message['timespent'] = timesestimate_tally
   
    return message


async def run_retro(team,retroName,retrotype,metric):
    today = datetime.date.today()
    logger.info(today)

    iterations = get_all_iterations(10477027)
    current_iteration = ""
    previous_iteration = ""
    for iteration in iterations:
        iteration_start = datetime.datetime.strptime(iteration['start_date'],"%Y-%m-%d").date()
        iteration_end = datetime.datetime.strptime(iteration['due_date'],"%Y-%m-%d").date()
        if iteration_start <= datetime.date.today() <= iteration_end:
            current_iteration = iteration['title']
        elif iteration_start >= datetime.date.today():
            future_iteration = iteration['title']
        else:
            previous_iteration = iteration['title']
    logger.info(f"previous title: {previous_iteration}")
    logger.info(f"iternation selected: {retroName}")
    if retroName == "current":
        getRetro = current_iteration
    elif retroName == "previous":
        getRetro = previous_iteration
    else:
        getRetro = current_iteration
    
    gl_issues = []
    response = get_issues(getRetro,1)
    
    gl_issues.extend(response.json())

    try:
        response.headers['X-Next-Page']
        page = int(response.headers['X-Next-Page'])
    except:
        page = int(response.headers['X-Total-Pages'])
        
    totalpage = int(response.headers['X-Total-Pages'])
    
    while page != totalpage:
        logger.info("Inside while loop")
        response = get_issues(getRetro,page)
        gl_issues.extend(response.json())
        page += 1
    
    gathered_issues = []
    for lissue in gl_issues:
        #need to filter down by label
        if LABEL_MAP['retro'][team] in lissue['labels']:
            # logger.info("Lables: {}".format(lissue['labels']))
            gathered_issues.append(lissue)

    g_label_counts = summarize_status(gathered_issues)
    if retrotype == "summary":
        #run KPI style reports.. no names of the innocent
        (iteration_weight, label_weights,timeestimate,timespent,timesestimate_tally,timespent_tally) = weight_by_team(gathered_issues)
        message = report_summary(iteration_weight,label_weights,len(gathered_issues),g_label_counts,team,timeestimate,timespent,timesestimate_tally,timespent_tally)
        return message
    else:
        (g_weight,g_timespent,g_timeestimate,g_count_talley) = weight_by_assignee(gathered_issues)
        if metric == "all":
            g_message = report(g_label_counts,g_weight,g_timespent,g_timeestimate,team,gathered_issues,g_count_talley)
        elif metric == "issues_by_status":
            print("blah blah")
            g_message = g_label_counts
        elif metric == "issues_by_weight":
            g_message = g_weight
        elif metric == "time_estimate":
            g_message = g_timeestimate
        elif metric == "time_spent":
            g_message = g_timespent
        elif metric == "tickets_by_user":
            g_message = g_count_talley
        return g_message

def run_retro2(team,retroName,retrotype,metric):
    today = datetime.date.today()
    logger.info(today)

    iterations = get_all_iterations(10477027)
    current_iteration = ""
    previous_iteration = ""
    for iteration in iterations:
        iteration_start = datetime.datetime.strptime(iteration['start_date'],"%Y-%m-%d").date()
        iteration_end = datetime.datetime.strptime(iteration['due_date'],"%Y-%m-%d").date()
        if iteration_start <= datetime.date.today() <= iteration_end:
            current_iteration = iteration['title']
        elif iteration_start >= datetime.date.today():
            future_iteration = iteration['title']
        else:
            previous_iteration = iteration['title']
    logger.info(f"previous title: {previous_iteration}")
    logger.info(f"iternation selected: {retroName}")
    if retroName == "current":
        getRetro = current_iteration
    elif retroName == "previous":
        getRetro = previous_iteration
    else:
        getRetro = current_iteration
    
    gl_issues = []
    response = get_issues(getRetro,1)
    
    gl_issues.extend(response.json())

    try:
        response.headers['X-Next-Page']
        page = int(response.headers['X-Next-Page'])
    except:
        page = int(response.headers['X-Total-Pages'])
        
    totalpage = int(response.headers['X-Total-Pages'])
    
    while page != totalpage:
        response = get_issues(getRetro,page)
        gl_issues.extend(response.json())
        page += 1
    
    gathered_issues = []
    for lissue in gl_issues:
        #need to filter down by label
        if LABEL_MAP['retro'][team] in lissue['labels']:
            gathered_issues.append(lissue)

    g_label_counts = summarize_status(gathered_issues)
    if retrotype == "summary":
        #run KPI style reports.. no names of the innocent
        (iteration_weight, label_weights,timeestimate,timespent,timesestimate_tally,timespent_tally) = weight_by_team(gathered_issues)
        return (iteration_weight, label_weights,timeestimate,timespent,timesestimate_tally,timespent_tally)
    else:
        (g_weight,g_timespent,g_timeestimate,g_count_talley) = weight_by_assignee(gathered_issues)
        (iteration_weight, label_weights,timeestimate,timespent,timesestimate_tally,timespent_tally) = weight_by_team(gathered_issues)
        if metric == "all":
            g_message = report(g_label_counts,g_weight,g_timespent,g_timeestimate,team,gathered_issues,g_count_talley)
            return g_message
        elif metric == "metrics":
            return (g_weight,g_timespent,g_timeestimate,g_count_talley,g_label_counts,len(gathered_issues),current_iteration)
