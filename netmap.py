#!/usr/bin/python

# Version 2.0
# Redone the data section of package

import select
import socket
import time
import sys
import struct
import getopt
import signal
import types
import string
import os
import os.path
import imp

import pygraphviz as pgv
from subprocess import *
import threading

import tools
import plugger
import timer

from node import Node,EndNode,cleanRoute, uniq
from impacket import ImpactDecoder, ImpactPacket
from sendPacket import *

# global flag for loop, has to be turned on
RUNNING = False

def usage():
    print "TODO"

def HandleSignal(sig, frame):
    global RUNNING
    if sig in (signal.SIGINT,signal.SIGTERM):
        #tell main loop to quit
        RUNNING = 0
    else:
        #ignore other signals
        print "SIGNAL PASSED"
        pass

def Trace(conf):
    ""
    global RUNNING
    waittime = conf['waittime']
    start_timeout = False
    t = timer.TimeLog()

    # Open a raw socket. Special permissions are usually required.
    s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)

    #signals
    oldInt = signal.signal(signal.SIGINT,HandleSignal)
    oldTerm = signal.signal(signal.SIGTERM,HandleSignal)
    oldHup = signal.signal(signal.SIGHUP,HandleSignal)

    endnodeList = {}
    cnt_traces = 0
    cnt_echoreply = 0
   
    localIp = 'localhost' 
        
    endnodeId = 0
    for ip in conf['targets']:
        endnodeList[endnodeId] = EndNode("localhost",ip,endnodeId,0)
        if conf['debug']:
            print "Just created this endnode: id:%d status:%d distance:%d"%(endnodeId,endnodeList[endnodeId].status,endnodeList[endnodeId].distance)
        endnodeId = endnodeId + 1

    #Let's abuse endnodeId while it still exits as a ip counter
    cnt_eta = endnodeId * conf['num_traces']

    doSweep = conf['doSweep']    
    t.log('trace')
    RUNNING = True
    while RUNNING:
        if doSweep:
            #we need a new PingSweep that eats empty endnodes not targets
            PingSweep(conf, endnodeList).start()
            if conf["verbose"] > 2 : print "Starting a PingSweep"
            doSweep = False
        # Wait for incoming replies.
        if s in select.select([s],[],[],1)[0]:
            reply = s.recvfrom(2000)[0]
            pingReply = PingReply(reply)
            if not pingReply.valid:
                if conf["debug"] : print "Invalid Package from %s [type %d]"% (pingReply.srcIp, pingReply.replyType)
                continue
           #We've recieved a valid package, lets ensure we reset a running timeout
            if start_timeout:
                if conf["verbose"] > 3 : print "Timeout cleared"
                start_timeout = False
            if (not endnodeList.has_key(pingReply.endnodeId)):
                #We've just catched a reply to a ping, we need to create a endnode and can place out local ip in Hop 0
                #This code might become obsolete as we prepare our endnodelist on forehand
                endnodeId = pingReply.endnodeId 
                endnodeList[endnodeId] = EndNode(pingReply.dstIp,pingReply.srcIp,endnodeId,pingReply.recv_ttl)
                endnodeList[endnodeId].status = 1
                cnt_echoreply = cnt_echoreply + 1 
                if pingReply.hopNr > 0:
                    if conf["debug"] : print "We should never get here, we have a endnode for a packet we've never recieved an icmp reply for"
                else:
                    #this is a ping sweep reply, if we need futher logging do it here!
                    if conf["verbose"] > 2 : print "Ping reply from %s" % pingReply.srcIp
            elif (pingReply.hopNr == 0):
                #We've got a pingreply on a endnode that we created on forehand, delete and create new
                endnodeId = pingReply.endnodeId 
                endnodeList[endnodeId] = EndNode(pingReply.dstIp,pingReply.srcIp,endnodeId,pingReply.recv_ttl)
                localIp = pingReply.dstIp
                endnodeList[endnodeId].status = 1
                cnt_echoreply = cnt_echoreply + 1 
            elif (endnodeList.has_key(pingReply.endnodeId)) and (pingReply.hopNr > 0):
                #we have a packet with a corresponding endnode
                #we don't count on multiple reply's for a certain hop
                endnodeList[pingReply.endnodeId].addHop(pingReply.hopNr,pingReply.srcIp,pingReply.dstIp)
                localIp = pingReply.dstIp
                if conf["verbose"] > 4 : print "Ping reply from %s in trace to %s [%d.%d]" % \
                                    (pingReply.srcIp,endnodeList[pingReply.endnodeId].targetIp,pingReply.endnodeId,pingReply.hopNr)
        elif (threading.activeCount() < conf['threads']) and (len(endnodeList) > 0):
            traceEndNode = TraceEndNode(conf['delay'])
            for endnodeId in endnodeList:
                if (endnodeList[endnodeId].status <= 2) and (len(traceEndNode.endnodes) < 10) :
                    traceEndNode.addEndNode(endnodeList[endnodeId])
                    endnodeList[endnodeId].status = 2
                    if (endnodeList[endnodeId].times_processed) >= conf['num_traces']:
                        endnodeList[endnodeId].status = 3
                    endnodeList[endnodeId].times_processed = endnodeList[endnodeId].times_processed + 1  
                    cnt_traces = cnt_traces + 1
                elif (threading.activeCount() >= conf['threads']) :
                    break
            if len(traceEndNode.endnodes) > 0:
                if conf['debug'] : print "%d threads running" % threading.activeCount()
                traceEndNode.start()
                if conf["verbose"] > 3 : print " [%d/%d]Starting a traceEndNode with %d endnodes" % (threading.activeCount(),conf['threads'],len(traceEndNode.endnodes))
                if conf["verbose"] > 2 : sys.stdout.write( "[%d/%d - %d%%]" % ( cnt_traces, cnt_eta, (cnt_traces*100) /cnt_eta)  )
                if conf['debug'] : print "%d threads running" % threading.activeCount()
                if conf['verbose'] : sys.stdout.flush()
            else:
                del(traceEndNode)
            
            if threading.activeCount() == 1:
                #If i'm correct we only arrive here when all endnodes have status >1
                # and we have no threads running
                if start_timeout:
                    #we've got a timeout
                    if (time.time() - start_timeout) > waittime:
                        RUNNING = False
                    if conf["verbose"] > 3 : print "%d seconds of timeout left"% (waittime - (time.time() - start_timeout))
                else:
                    #let's set a timeout we're going down :)
                    start_timeout = time.time()
                    if conf["verbose"] > 3 : print "Timeout Set"
    t.log('trace')

    if conf["verbose"] > 2 : print "Done bursting and collecting in %d seconds including idle period"% ( t.runtime('trace'))

    t.log('clean')
    allNodes = {}

    # we run trough the ennodeLists and their routes, we create a new node for all of those with a type.
    for endnodeId in endnodeList:
        # we do this somewhere else to filter out unroutable muk
        #ip  = endnodeList[endnodeId].targetIp
        #if allNodes.has_key(ip):
        #    allNodes[ip].target = True
        #else:
        #    allNodes[ip] = Node(ip,target=True)
        for routeId, route in endnodeList[endnodeId].routes.iteritems():
            lenRoute = len(route)
            route[0] = localIp
            #we will reference unknown endnodes to the endnode before
            #if target is not at end of route we add it.
            # we only want to do this if the old length > 1 to ensure non routable ip's don't show
            if (not  route[route.keys().__reversed__().next()] == endnodeList[endnodeId].targetIp) and (lenRoute > 1):
                route[route.keys().__reversed__().next()+1] = endnodeList[endnodeId].targetIp
                
            route = cleanRoute(route)
            for hop, ip in route.iteritems():
                lenRoute = lenRoute -1
                if isValidIp(ip):
                    if not allNodes.has_key(ip):
                        allNodes[ip] = Node(ip)
                    if lenRoute > 0:
                        allNodes[ip].type = 'router'
                    elif not allNodes[ip].type:
                        allNodes[ip].type = 'endpoint'
                    if ip in conf['targets']:
                        allNodes[ip].target = True
            if conf["verbose"] > 3 : print "Route %d in EndNodeId %d cleaned" % (routeId,endnodeId)
        if conf["verbose"] > 3 : print "EndNodeId %d cleaned" % endnodeId
    if conf["verbose"] > 1 : print "Routes cleaned"
    t.log('clean')
    
    #Time to run plugins
    if conf['plugins']:
        t.log('plugins')
        runPlugins(conf,t,allNodes)
        t.log('plugins')

    #Here we have allNodes with plugin results
    #we also still have EndnodeList with traceroutes

    #now parse each endnode we will get a lot of weird solutions where a NULL hop is. maybe delete this endnode?
    #print graph. We want this code out. from here we go reporting.
    t.log('parse')
    linkedHosts = []

    cnt_endnodes = 0
    cnt_routes = 0
    total_hops = 0
    cnt_targets = len(conf['targets'])

    for endnodeId in endnodeList:
        if conf["verbose"] > 3 : print "We have %d routes to: %s " % (len( endnodeList[endnodeId].routes) ,endnodeList[endnodeId].targetIp)
        for route in endnodeList[endnodeId].routes:
            for hop in endnodeList[endnodeId].routes[route]:
                if conf["verbose"] > 3 : print "\t%d\t%s" % (hop ,endnodeList[endnodeId].routes[route][hop])
                if hop > 0:
                    if endnodeList[endnodeId].routes[route].has_key(hop-1):
                        fromIp = endnodeList[endnodeId].routes[route][hop-1]
                        toIp = endnodeList[endnodeId].routes[route][hop]
                        linkedHosts.append( (fromIp , toIp) )
                    else:
                        if conf["verbose"] > 2 : print "endnodeList[%d].routes[%d] has no key %d. graph might have errors"%(endnodeId,route,hop-1)
                total_hops = total_hops + 1
            cnt_routes = cnt_routes +1
        cnt_endnodes = cnt_endnodes + 1
    #linkedHosts = uniq(linkedHosts)
    cnt_uniq_relations = len(uniq(linkedHosts))
    cnt_relations = len(linkedHosts)

    ###### following area is parsing, we should move this out!
    t.log('parse')

    G=pgv.AGraph(strict=True,directed=False)
    G.add_edges_from(linkedHosts, color='blue')

    #G.graph_attr['overlap']='False'
    #G.graph_attr['overlap']='orthoyx'
    #G.graph_attr['overlap_scaling']='5'
    #G.graph_attr['sep'] = '0'
    G.graph_attr['ratio'] = 'auto'
    G.graph_attr['ranksep'] = '3'
    #G.graph_attr['smoothing']='True'
    #G.graph_attr['packMode'] = 'clust'
    G.node_attr['fontname'] = 'Times-Roman'
    G.node_attr['fontsize'] = '12'
    G.node_attr['shape']='Mrecord'
    G.graph_attr['rankdir'] = 'LR'
    G.edge_attr['color']='blue'
    #G.graph_attr['ratio'] = 'fill'

    for node in G.nodes():
        label = "%s"% node
        if allNodes.has_key(node):
            for k,v in allNodes[node].plugins.iteritems():
                label = "%s|{%s|%s}"% (label, k, v)
        node.attr['label'] = label.replace(" ","\ ")

    #if conf['extras']:
    #    for node in G.nodes():
    #        node.attr['URL'] = "http://\N"
    t.log('parse')
 
    G.write("img/test.dot")
    if conf["verbose"] > 2 : print ".dot image was written to disk!"

    t.log('parse')
    t.log('draw')

    #G.layout()
    #G.draw("img/test.%s.svg"%type, prog='dot')
    #G.draw("img/test.png"%type, prog='dot')
    t.log('draw')
    
    if conf["verbose"] > 3 : print "config [%s]" % str(conf)
    if conf["verbose"] > 0 : 
        print "We had %d targets and %d echo replies "%(cnt_targets,cnt_echoreply)
        print "we've executed %d traceroutes"%(cnt_traces)
        print "We've found %d relations. (%d unique relations)"% (cnt_relations, cnt_uniq_relations)
        print "We've traced %d targets in %d  traceroutes with an average hopcount of %d."%(cnt_endnodes,cnt_routes,(total_hops/cnt_traces))
        t.report()
        print "Succesfully stopped"

    #signals
    signal.signal(signal.SIGINT,oldInt)
    signal.signal(signal.SIGINT,oldTerm)
    signal.signal(signal.SIGINT,oldHup)





def runPlugins(conf,t,allNodes):
    #Time to run plugins
    pluginpath = os.path.join(os.path.dirname(imp.find_module("plugger")[1]), "plugins/")
    pluginfiles = [fname[:-3] for fname in os.listdir(pluginpath) if fname.endswith(".py")]

    if not pluginpath in sys.path:
        sys.path.insert(0,pluginpath)
    #imported_modules = [__import__(fname) for fname in pluginfiles]
    plugins = {}
    for fname in pluginfiles:
        try:
            plugins[fname] = __import__(fname)
        except:
            pass
    if conf['verbose'] > 3: print plugins

    ips = allNodes.keys()

    cq=plugger.CallQueue(max_default_consumer_threads=conf['threads'])
    for plugin in plugins:
        t.log("plugin.%s"% plugin)
        #plugins[plugin]
        for ip in ips:
            try:
                cqitem=cq.call_and_collect(plugins[plugin].work,(ip,allNodes[ip],))      #schedule
            except:
                if conf['debug'] : print "exception in %s for %s"% (plugin,ip)
                pass
        while not cq.is_done():
            for cqitem in cq.get_next_collected():       #harvest
                ret = cqitem.get_return()
                if conf['verbose'] > 2: print plugin,cqitem.args, ">>%s [%s %s]"% (cqitem.args[0],plugins[plugin].name(),ret)
                allNodes[cqitem.args[0]].addPluginResults(plugins[plugin].name(), ret)
            #print ".",
            time.sleep(0.001)
        t.log("plugin.%s"% plugin)



def main(argv):
    "Let's : let's catch"

    # some conf value's in dict

    conf = {"verbose":1,"debug":False,"quiet":False, "inputfile":"iplist.txt","threads":25,"waittime":5,"delay":0,"num_traces":5,"doSweep":True,"resolve":False,"plugins":False}

    try:
            optlist, list = getopt.getopt(argv[1:],"qhvPrDi:d:t:n:w:p", ["quiet","help","nosweep","resolve","debug","input=","delay=","threads=","num_traces=","waittime=","plugins"])
    except getopt.GetoptError, err:
        #print helpinfo and exit
        print str(err) #will tell what option isn't recognized
        usage()
        sys.exit(1)

    for opt in optlist:
        if opt[0] == "-v":
            conf["verbose"] = conf["verbose"] + 1
        elif opt[0] in ("-q","--quiet"):
            conf["quiet"] = True
        elif opt[0] in ("-i","--input"):
            conf["inputfile"] = opt[1]
        elif opt[0] in ("-d","--delay"):
            conf["delay"] = int(opt[1])
        elif opt[0] in ("-t","--threads"):
            conf["threads"] = int(opt[1])
        elif opt[0] in ("-n","--num_traces"):
            conf["num_traces"] = int(opt[1])
        elif opt[0] in ("-w","--waittime"):
            conf["waittime"] = int(opt[1])
        elif opt[0] in ("-P","--nosweep"):
            conf["doSweep"] = False
        elif opt[0] in ("-r","--resolve"):
            conf["resolve"] = True
        elif opt[0] in ("-p","--plugins"):
            conf["plugins"] = True
        elif opt[0] in ("-D","--debug"):
            conf["debug"] = True
        elif opt[0] in ("-h","--help"):
            usage()
            sys.exit(0)

    #One sanity check
    if conf['quiet']:
        if conf['verbose'] > 1:
            print "Please don't use -q or --quiet in combination with -v"
            sys.exit(0)
        conf['verbose'] = 0

    #sanity check on delay, including conversion to seconds
    if (conf['delay'] < 0) or (conf['delay'] > 5000):
        print"Please us a delay between 0 and 5000 milliseconds"
        sys.exit(0)
    if not (conf['delay']is 0): conf['delay'] = float(conf['delay']) / 1000

    ## sanity check on threads
    if not ((conf['threads'] > 2) and (conf['threads'] < 500)):
        print"please choose a sane thread number, 1 is neede for parent, 1 for child zo all between 2 and 500 is ok."
    # Opening list of IP's
    try:
        input_fp = open(conf["inputfile"], "r")
    except IOError, (ErrorNumber,ErrorMessage):
        if ErrorNumber == 2: #file not found, most likely
            print "- Sorry, file \"%s\" not found, please feed me a file with only ipaddresses" % (conf["inputfile"])
        else:
            print "- Congrats, you managed to trigger errornumber %s" % (ErrorNumber)
            print "     " + ErrorMessage
        sys.exit(1)

    if conf["verbose"] > 1 : print "- %s opened" % conf["inputfile"]

    if conf['verbose'] > 0:
        print "config [%s]" % str(conf)

    # Read the IP file and test all ip's for validity   
    ips = input_fp.readlines()
    input_fp.close()

    valid_ips = []
    for ip in ips:
        #check if all ip's are ok
        if isValidIp(ip) == False :
            quit = True
            if conf["verbose"] > 2 : print "- %s is not a valid IP address!" % (ip.strip())
        else:
            valid_ips.append(ip.strip())
    
    conf['targets'] = valid_ips

    Trace(conf)

if __name__ == "__main__":
        main(sys.argv)

