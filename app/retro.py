
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


def get_all_iterations(CONFIG_MAP):
    """Get the current iteration name

    Args:
        CONFIG_MAP (dict): Configuration

    Returns:
        str: Iteration name
    """
    gl_iterations = []
    gl_iterations = requests.get(
        CONFIG_MAP['GITLAB_URL'] + "groups/{}/iterations?state=current".format(CONFIG_MAP['iteration_group']),
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
        elif iteration_start >= datetime.date.today():
            future_iteration = iteration['title']
        else:
            previous_iteration = iteration['title']
    logger.info("Inside Get Iterations: {}".format(current_iteration))
    return current_iteration


def iteration_summarize_status(issues,CONFIG_MAP):
    """Run iteration based metrics

    Args:
        issues (dict): Issues to interogate
        CONFIG_MAP (dict): configuration

    Returns:
        label_talley (Counter): Count of issues by label
        priority_talley (Counter): Count of issues by priority
        severity_talley (Counter): Count of issues by severity
    """
    label_tally = Counter()
    priority_tally = Counter()
    severity_tally = Counter()
   
    for issue in issues:
        for label in issue['labels']:
            if re.search(CONFIG_MAP['dev_label_prefix'],label):
                label_tally[label] += 1
            elif re.search(CONFIG_MAP['qa_label_prefix'],label):
                label_tally[label] += 1
            elif re.search(CONFIG_MAP['priority_label_prefix'],label):
                priority_tally[label] += 1
            elif re.search(CONFIG_MAP['severity_label_prefix'],label):
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
    


def team_based_metrics(issues,CONFIG_MAP):
    """Team based metrics

    Args:
        issues (dict): Issues to interrogate
        CONFIG_MAP (dict): Configruation

    Returns:
        [type]: [description]
        weight_tally (Counter): Weight by user
        timespent_tally (Counter): Time spent total by user
        timesestimate_tally (Counter): Time estimate total by user 
        user_tally (Counter): Ticket count by user
        status_tally (Counter): Ticket status by user
        category_tally (Counter): Ticket category by team
        priority_tally (Counter): Ticket priority by team
        severity_tally (Counter): Ticket severity by team
        milestone_tally (Counter): Milestone count by team
        epic_tally (Counter): Epic count by team
        participant_tally (Counter): not used
    """
    
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
    timeestimate = 0
    count = 1
    for issue in issues:
        for users in issue['assignees']:
            user = users['name']
            weight = 0
            #If isssue is closed don't count the weight
            if issue['state'] == "opened":
                if issue['weight'] is None:
                    weight = 0
                else:
                    weight = issue['weight']
                if issue['time_stats']['time_estimate'] is None:
                    timeestimate = 0
                else:
                    timeestimate = issue['time_stats']['time_estimate']//3600
            if issue['time_stats']['total_time_spent'] is None:
                timespent = 0
            else:
                timespent = issue['time_stats']['total_time_spent']//3600
            weight_tally[user] += weight
            timespent_tally[user] += timespent
            timesestimate_tally[user] += timeestimate
            user_tally[user] += 1
        for label in issue['labels']:
            if re.search(CONFIG_MAP['dev_label_prefix'],label):
                status_tally[label] += 1
                if label == CONFIG_MAP['done_status_label']:
                    # participant_tally = get_participants(CONFIG_MAP,issue['_links']['self'],participant_tally)
                    for participants in issue['assignees']:
                        participant = participants['name']
                        participant_tally[participant] += 1
            elif re.search(CONFIG_MAP['qa_label_prefix'],label):
                status_tally[label] += 1
            elif re.search(CONFIG_MAP['issue_status_prefix'],label):
                category_tally[label] += 1
            elif re.search(CONFIG_MAP['priority_label_prefix'],label):
                priority_tally[label] += 1
            elif re.search(CONFIG_MAP['severity_label_prefix'],label):
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

def iteration_based_metrics(issues,CONFIG_MAP):
    """Iteration based metircs, not specific to a team

    Args:
        issues (dict): Issues to interrogate
        CONFIG_MAP (dict): Configuration

    Returns:
        [type]: [description]
        overall_weight (Counter): Weight total for the interation
        label_tally (Counter): Issues by label status
        overall_timeestimate (int): Overall time estimate for the iteration
        overall_timespent (int): Overall time spent for the iteration
        timesestimate_tally (Counter): Time estimated by label for the interation
        timespent_tally (Counter): Time spent by label for the interation
        epic_tally (Counter): Number of issues per epic in the interation 
        milestone_tally (Counter): Number of milestones in the iteration
    """
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
            if re.search(CONFIG_MAP['dev_label_prefix'],label):
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
        dict: issues gathered from this pull
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
        # gl_params = "groups/{}/issues?labels={}&per_page=100&page={}&state={}&not[labels]={}&iteration_title={}".format(project_id,includes_labels,page,issue_state,exclude_labels,iteration)

    response = requests.get(
        CONFIG_MAP2['GITLAB_URL'] + gl_params,
        headers=CONFIG_MAP2['GITLAB_HEADERS'],
        verify=True
    )
    logger.debug("issues returned: {}".format(len(response.json())))
    return response

# def locate_issues(÷project_id,filter_labels,iteration):
def locate_issues(lCONFIG_MAP,filter_labels,iteration):
    """Function to get all of the issues

    Args:
        lCONFIG_MAP (dict): Configuration
        filter_labels (str): Label to filter by
        iteration (str): Iteration name

    Returns:
        dict: Dictionary of issues
    """
    #query issues for a project and then filter down by labels supplied
    gl_issues = []

    response = get_issues(lCONFIG_MAP.copy(),filter_labels,1,iteration)
    gl_issues.extend(response.json())

    try:
        response.headers['X-Page']
        page = int(response.headers['X-Page'])
        logger.debug("try page: {}".format(page))
    except:
        page = int(response.headers['X-Total-Pages'])
        logger.debug("except page: {}".format(page))
       
    totalpage = int(response.headers['X-Total-Pages'])

    logger.debug("page: {}".format(page))  
    logger.debug("totalpage: {}".format(totalpage)) 
    
    while page != totalpage:
        page += 1
        response = get_issues(lCONFIG_MAP.copy(),filter_labels,page,iteration)
        gl_issues.extend(response.json())
    
    return(gl_issues)


def get_group_issues(CONFIG_MAP):
    """Filter issues for a group

    Args:
        CONFIG_MAP (dict): Configuration

    Returns:
        gl_issues (dict): Filtered list of issues for the team label
        getRetro (str): Name of the iteration
    """

    getRetro = get_all_iterations(CONFIG_MAP)
    logger.info("Current Iteration: {}".format(getRetro))

    gl_issues = locate_issues(CONFIG_MAP,CONFIG_MAP['team_label'],getRetro)

    return (gl_issues, getRetro)

def get_issue_counts(CONFIG_MAP,gl_issues):
    """Get counts of issues in backlog and the iteration.  Runs for every team in CONFIG_MAP['teams']

    Args:
        CONFIG_MAP (dict): Configuration
        gl_issues (dict): Gathered issues to interogate
    
    Returns:
        dict: Counts by iteration and backlog for each team

    NOTES:  the teamextract assumes that your labels have a suffix such as GS or something else.
            This ties the team name to the team label.  For instance Backend GS to backend
    """

    results = {}
    team_labels = []

    # Build teams that we need
    for team in CONFIG_MAP['teams']:
        results[team] = {
            "iteration": 0,
            "backlog": 0
        }
        team_labels.append(CONFIG_MAP[team])
   
    for issue in gl_issues:
        for label in issue['labels']:
            if label in team_labels:
                teamextract = label.split(' ')[0].lower()
                results[teamextract]['iteration'] += 1
    
    # Now look at backlog
    bl_all_issues = locate_issues(CONFIG_MAP,CONFIG_MAP['team_label'],"backlog")
    bl_issues = []
    for issue in bl_all_issues:
        for label in issue['labels']:
            if label == CONFIG_MAP['backlog_label']:
                bl_issues.append(issue)
    for issue in bl_issues:
        for label in issue['labels']:
            if label in team_labels:
                teamextract = label.split(' ')[0].lower()
                results[teamextract]['backlog'] += 1

    # return(fe,be,sfdc)
    return(results)

def run_retro2(team,gl_issues,CONFIG_MAP):
    """

    Args:
        team (str): Name of the team to run report for
        gl_issues (dict): List of issues to run through

    Returns:
        list: list of dicts that contain metric data
    """
    today = datetime.date.today()

    # ## All issues gathered
    gathered_issues = team_filter(team,gl_issues,CONFIG_MAP)

    return team_based_metrics(gathered_issues,CONFIG_MAP)

def team_filter(team,gl_issues,CONFIG_MAP):
    """Filter issues by team

    Args:
        team (str): Name of the team to filter for
        gl_issues (dict): Issues to interrogate
        CONFIG_MAP (dict): Configuration

    Returns:
        dict: Filtered list of issues
    """
    ## All issues gathered
    gathered_issues = []
    for lissue in gl_issues:
        #need to filter down by label.
        if CONFIG_MAP[team] in lissue['labels']:
            if CONFIG_MAP['team_label'] in lissue['labels']:
                gathered_issues.append(lissue)
    logger.info("Number of issues: {}".format(len(gathered_issues)))
    return gathered_issues

def run_team_issue_activity(team,gl_issues,CONFIG_MAP):
    """Look at label activity to see who which users are finished with work and moved to QA.  Lookup each issue in the interation

    Args:
        team (str): Which team to run against
        gl_issues (dict): Issues to interrogate
        CONFIG_MAP (dict): Configruation

    Returns:
        dict: count of tickets finished by user
    """
    logger.info("Runing Team Issue Activity")
    gathered_issues = team_filter(team,gl_issues,CONFIG_MAP)


    engComplete = Counter()
    for issue in gathered_issues:
        label_events = requests.get(
            issue['_links']['self'] + '/resource_label_events',
            headers=CONFIG_MAP['GITLAB_HEADERS'],
            verify=True
        ).json()
        
        for labels in label_events:
            if isinstance(labels['label'], type(None)):
                continue
            else:
                if labels['label']['name'] == CONFIG_MAP['eng_done_status'] and labels['action'] == "add":
                    username = labels['user']['name']
                    engComplete[username] += 1
    logger.info("Finished processing run_team_issue_activity")
    return engComplete

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
    reldate = re.search('(\d+-\d+-\d+)',releases[0]['released_at']).group(1)
    rels = {
        "current": releases[0]['tag_name'],
        "current_date": releases[0]['released_at'],
        "short_date": reldate,
        "total": len(releases)
    }
    
    return rels
