
from fastapi import responses
import requests
import datetime
import re
from collections import Counter
import os
import logging

logFormatter = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(format=logFormatter, level=logging.INFO)
logger = logging.getLogger(__name__)


def get_all_iterations(CONFIG_MAP,retroName="Current"):
    gl_iterations = []
    gl_iterations = requests.get(
        CONFIG_MAP['GITLAB_URL'] + "groups/{}/{}".format(CONFIG_MAP['iteration_group'],"iterations"),
        headers=CONFIG_MAP['GITLAB_HEADERS'],
        verify=True
    ).json()

    current_iteration = ""
    previous_iteration = ""
    for iteration in gl_iterations:
        iteration_start = datetime.datetime.strptime(iteration['start_date'],"%Y-%m-%d").date()
        iteration_end = datetime.datetime.strptime(iteration['due_date'],"%Y-%m-%d").date()
        if iteration_start <= datetime.date.today() <= iteration_end:
            current_iteration = iteration['title']
            # print("current iteration title: {}".format(iteration['title']))
        elif iteration_start >= datetime.date.today():
            future_iteration = iteration['title']
        else:
            previous_iteration = iteration['title']

    return current_iteration


def iteration_summarize_status(issues):
    label_tally = Counter()
    priority_tally = Counter()
    severity_tally = Counter()
   
    for issue in issues:
        for label in issue['labels']:
            if re.search('Dev GS::',label):
                label_tally[label] += 1
            elif re.search('Priority GS::',label):
                priority_tally[label] += 1
            elif re.search('Severity GS::',label):
                severity_tally[label] += 1
    return (label_tally,priority_tally,severity_tally)

def get_participants(CONFIG_MAP,iid,in_tally):
    p_tally = Counter()
    gl_participants = requests.get(
        iid + '/participants',
        headers=CONFIG_MAP['GITLAB_HEADERS'],
        verify=True
    ).json()

    if gl_participants:
        for user in gl_participants:
            in_tally[user['name']] += 1
    return in_tally
    


def team_based_metrics(issues):
    weight_tally = Counter()
    timespent_tally = Counter()
    timesestimate_tally = Counter()
    user_tally = Counter()
    status_tally = Counter()
    category_tally = Counter()
    priority_tally = Counter()
    severity_tally = Counter()
    epic_tally = Counter()
    milestone_tally = Counter()
    participant_tally = Counter()

    count = 1
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

            weight_tally[user] += weight
            timespent_tally[user] += timespent
            timesestimate_tally[user] += timeestimate
            user_tally[user] += 1
        for label in issue['labels']:
            if re.search('Dev GS::',label):
                status_tally[label] += 1
                if label == "Dev GS::Done":
                    # participant_tally = get_participants(CONFIG_MAP,issue['_links']['self'],participant_tally)
                    participant_tally = ""
            elif re.search('Issue GS::',label):
                category_tally[label] += 1
            elif re.search('Priority GS::',label):
                priority_tally[label] += 1
            elif re.search('Severity GS::',label):
                severity_tally[label] += 1
        if issue['milestone']:
            if issue['milestone']['title'] == "":
                milestone_tally["No Milestone"] += 1
            else:
                milestone_tally[issue['milestone']['title']] += 1
        if issue['epic']:
            if issue['epic']['title'] == "":
                epic_tally["No Epic"] += 1
            else:
                epic_tally[issue['epic']['title']] += 1

    return (weight_tally,timespent_tally,timesestimate_tally,user_tally,status_tally,category_tally,priority_tally,severity_tally,milestone_tally,epic_tally,participant_tally)

def iteration_based_metrics(issues):
    overall_weight = 0
    w_tally = Counter()
    label_tally = Counter()
    timespent_tally = Counter()
    timesestimate_tally = Counter()
    overall_timespent = 0
    overall_timeestimate = 0
    epic_tally = Counter()
    milestone_tally = Counter()
    
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
        if issue['milestone']:
            if issue['milestone']['title'] == "":
                milestone_tally["No Milestone"] += 1
            else:
                milestone_tally[issue['milestone']['title']] += 1
        if issue['epic']:
            if issue['epic']['title'] == "":
                epic_tally["No Epic"] += 1
            else:
                epic_tally[issue['epic']['title']] += 1
        
    return (overall_weight, label_tally,overall_timeestimate,overall_timespent,timesestimate_tally,timespent_tally,epic_tally,milestone_tally)
        
    
def get_issues(CONFIG_MAP2,includes_labels,page=1,iteration="Current",exclude_labels=False,issue_state="all"):
    """Find all the correct issues.  Handles pagination and includes/excludes

    Args:
        project_id (int): Where should we look for issues?
        includes_labels (str): Labels to search for
        page (int, optional): Page to start search from. Defaults to 1.
        iteration(str): Name of the iteration
        exclude_labels (str, optional): labels to filter out. Defaults to False.
        issue_state (str, optional): Look for opened or closed issues?. Defaults to "opened".

    Returns:
        [type]: [description]
    """

    gl_params = "groups/{}/issues?labels={}&per_page=100&page={}".format(CONFIG_MAP2['parent_group'],includes_labels,page,issue_state)
    
    if iteration == "backlog":
        issue_state = "opened"
    else:
        gl_params = gl_params + "&iteration_title={}".format(iteration)
    
    if issue_state:
        gl_params = gl_params + "&state={}".format(issue_state)
    
    if exclude_labels:
        gl_params = gl_params + '&not[labels]={}'.format(exclude_labels)
        
    response = requests.get(
        CONFIG_MAP2['GITLAB_URL'] + gl_params,
        headers=CONFIG_MAP2['GITLAB_HEADERS'],
        verify=True
    )
    logger.debug("issues returned: {}".format(len(response.json())))
    return response


def locate_issues(lCONFIG_MAP,filter_labels,iteration):
    #query issues for a project and then filter down by labels supplied
    gl_issues = []

    response = get_issues(lCONFIG_MAP.copy(),filter_labels,1,iteration)
    gl_issues.extend(response.json())

    try:
        response.headers['X-Page']
        page = int(response.headers['X-Page'])
        logger.info("try page: {}".format(page))
    except:
        page = int(response.headers['X-Total-Pages'])
        logger.info("except page: {}".format(page))
       
    totalpage = int(response.headers['X-Total-Pages'])

    logger.info("page: {}".format(page))  
    logger.info("totalpage: {}".format(totalpage)) 
    
    while page != totalpage:
        page += 1
        response = get_issues(lCONFIG_MAP.copy(),filter_labels,page,iteration)
        gl_issues.extend(response.json())
    
    return(gl_issues)


def get_group_issues(lCONFIG_MAP):

    getRetro = get_all_iterations(lCONFIG_MAP)

    gl_issues = locate_issues(lCONFIG_MAP,"Core GS",getRetro)

    return (gl_issues, getRetro)

def get_issue_counts(CONFIG_MAP,gl_issues):
    fe = {
        "iteration": 0,
        "backlog": 0
    }
    be = {
        "iteration": 0,
        "backlog": 0
    }
    sfdc = {
        "iteration": 0,
        "backlog": 0
    }
    for issue in gl_issues:
        for label in issue['labels']:
            if re.search("Backend GS",label):
                be['iteration'] += 1
            elif re.search("Frontend GS",label):
                fe['iteration'] += 1
            elif re.search("Salesforce GS",label):
                sfdc['iteration'] += 1
    # Now look at backlog
    bl_all_issues = locate_issues(CONFIG_MAP,"Core GS","backlog")
    bl_issues = []
    for issue in bl_all_issues:
        for label in issue['labels']:
            if label == CONFIG_MAP['backlog_label']:
                bl_issues.append(issue)
    for issue in bl_issues:
        for label in issue['labels']:
            if re.search("Backend GS",label):
                be['backlog'] += 1
            elif re.search("Frontend GS",label):
                fe['backlog'] += 1
            elif re.search("Salesforce GS",label):
                sfdc['backlog'] += 1

    return(fe,be,sfdc)

def run_retro2(team,gl_issues,CONFIG_MAP):
    """[summary]

    Args:
        team (str): Name of the team to run report for
        gl_issues (dict): List of issues to run through

    Returns:
        list: list of dicts that contain metric data
    """
    today = datetime.date.today()

    ## All issues gathered
    gathered_issues = []
    for lissue in gl_issues:
        #need to filter down by label.  Need to have team and Core GS labels
        if CONFIG_MAP[team] in lissue['labels']:
            if CONFIG_MAP['coredev'] in lissue['labels']:
                gathered_issues.append(lissue)
    logger.info("Number of issues: {}".format(len(gathered_issues)))

    return team_based_metrics(gathered_issues)


def get_releases(CONFIG_MAP):
    """Get the latest release name from the project

    Args:
        project_id (int): ID of the project to find releases in

    Returns:
        str: Version of the latest release  
    """

    releases = requests.get(
        CONFIG_MAP['GITLAB_URL'] + "projects/{}/releases?&order_by=released_at&sort=desc".format(CONFIG_MAP['releases_project']),
        headers=CONFIG_MAP['GITLAB_HEADERS'],
        verify=True
    ).json()
    rels = {
        "current": releases[0]['tag_name'],
        "current_date": releases[0]['released_at'],
        "total": len(releases)
    }
    
    return rels
