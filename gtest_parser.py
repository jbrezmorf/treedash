import sys
import os
import xml.etree.ElementTree as ET
import platform
import re
import tempfile
import subprocess
import dateutil.parser
import json

class ExcWrongTag(Exception):
    def __init__(self, value):
        self.value=value
    def __str__(self):
        return "Wrong tag: " + repr(self.value)
      
class ExcMessage(Exception):
    def __init__(self, value):
        self.value=value
    def __str__(self):
        return repr(self.value)      
        
def make_node(type):
    return { 'attrib' : { 'type' : type }, 'childs' : {} }

def parse_gtest_xml( filename ):
    """
    Returns dictionary with data from a google test JUnit XML report.
    Dictionary structure:
    { attrib: { type: "test" }
      childs: {
          suite1 : {
            attrib: { type: "suite", disabled: false }
            childs: { 
              case1: { 
                attrib: {type: "case", run: true, time: 123  }
              }}}}}
     
    """
    tree = ET.parse(filename)
    testsuits = tree.getroot()
    
    if (testsuits.tag != "testsuites"):
        raise ExcWrongTag(testsuits.tag)
   
    result=make_node("test")
    for suite in testsuits:
        if (suite.tag != "testsuite"):
            raise ExcWrongTag(suite.tag)
        
        r_suite=result['childs'][suite.attrib['name']]=make_node("suite")        
        r_suite['attrib']['disabled']= ( suite.attrib['disabled'] != 0 )
        for case in suite:
            if (case.tag != "testcase"):
                raise ExcWrongTag(case.tag)
            
            r_case=r_suite['childs'][case.attrib['name']]=make_node("case")
            r_case['attrib']['time']=case.attrib['time']
            r_case['attrib']['run']= ( case.attrib['status'] == 'run' )
    return result        

def get_host_info():
    """
    Returns a dictionary with information about testrun environment, namely
    specification of host and code version
    {
      os:               # {win|linux}_{32|64}
      hostname:         # local host name, address 
      uname:
      frequency:        # in MHz
      benchmark:        # time of sample code snipet
    """
    result={}
    uname=platform.uname()
    result['uname']={
      'system':uname[0],
      'hostname':uname[1],
      'release':uname[2],
      'version':uname[3],
      'machine':uname[4],
      'processor':uname[5]}
    if (uname[0] == "Linux") :
        subprocess.check_output(['cat','/proc/cpuinfo'])

    # frequency from system  
    result['frequency']=None
    if (uname[0] == "Windows") :
        import wmi
        
        c=wmi.WMI()
        result['frequency']=float(c.Win32_Processor()[0].MaxClockSpeed)
    else :
        out = subprocess.check_output(['cat','/proc/cpuinfo'])
        match=re.search('cpuMHz\s*:      ([0-9.]*)',out)
        if (match) :
            result['frequency']=float(match.group(1))
    
    # simple speed test
    import timeit
    time=timeit.Timer('for i in range(0,100) : x+=x*list[x%1000];','x=1;list=range(1,1000)').timeit(100)
    print time
    result['benchmark']=time
        
    result['os']=uname[0]+"_"+uname[4]
    result['hostname']=platform.node() 
    
    return result

def get_commit_info(commit_range) :
    result = []
    item = {}
    out=subprocess.check_output(['git', 'log', commit_range])
    for line in out.splitlines():
        if (line.startswith("commit")) :
            print item
            if (item != {}) : result.append(item)
            item={}
            item["hash"] = re.sub("^commit","",line).strip()
            item["message"]=""
        elif (line.startswith("Author:")) :
            item["author"] = re.sub("^Author:","",line).strip()
        elif (line.startswith("Date:")) :
            date_str=re.sub("^Date:","",line).strip() 
            item["date_str"] = date_str
        elif (line.startswith("  ")) :
            item["message"] += line + "\n"
    result.append(item)        
    return result        
        
    
def get_branch_info():
    """
      { git_branch,
        git_remote,
        git_commit = 
        { hash, message, author, date_str }
      }  
    """
    result={}
    
    out=subprocess.check_output(['git', 'branch', '--list', '-vv'])
    match=re.search('\* (\w*)\s*([0-9a-f]*) (\[(.*)\] )?(.*)\n',out)    
    result['git_branch']=match.group(1)
    result['git_commit']=get_commit_info("HEAD^..HEAD")[0]
    remote_branch=match.group(4)    
    
    print remote_branch
    if (remote_branch != None) :
        remote=re.match('(\w*)/(.*)', remote_branch).group(1)
        out=subprocess.check_output(['git','remote','-v'])
        result['git_remote_branch']=re.search('('+remote+')\s*([^ ]*) \(fetch\)\n', out).group(2)
    else :
        result['git_remote_branch']=None
    
    #result['git_describe']=subprocess.check_output(['git','describe'])  
    return result
  
  
  
def get_exam_data():
    return {}
  
  
  
def send_to_server():
    import requests
    
    url='http://localhost:8000'
    headers={'content-type': 'application/json'}
    
    report={
      "request-type" : "add_report",
      'host_info' : get_host_info(),
      'branch_info' : get_branch_info(),
      'exam_data' : get_exam_data()
    }  
    
    r=requests.post(url, data=json.dumps(report),headers=headers)
    
    if (r.status_code == 200 and r.headers['content-type'] == "application/json") :
        last_commit=r.json()['last_commit']
        if (last_commit == 0) :
            commits=get_commit_info("")
        else :
            commits=get_commit_info(last_commit+"..HEAD")
        report={
            "request-type" : "add_to_branch",
            "branch_data" : commits
        }    
        r=requests.post(url, data=json.dumps(report),headers=headers)    
    
    if (r.status_code != 200) :
        raise(ExcMessage("Server do not accept the report."))
  

# Main -----------------------------------

send_to_server()

#print json.dumps(get_commit_info("HEAD"), indent=2)
