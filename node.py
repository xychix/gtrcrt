class Node:
    def __init__(self, ip, type=None, target=False):
        self.ip = ip
        self.hostname = ip
        #node is default, we expect to work with 'endnode', 'router', ...
        self.type = type
        self.target = target
        self.plugins = {}
    
    def addPluginResults(self, name,lines):
        self.plugins[name] = lines 

class EndNode:
    def __init__(self, localIp, targetIp, nodeId, ttl_recv):
        self.targetIp = targetIp
        self.endnodeId = nodeId
        self.status = 0
        self.times_processed = 0
        #self.hops = {}
        self.routes = {}
        self.addHop(0,localIp,localIp)
        self.distance = self.detDistance(ttl_recv)

    def addHop(self,hop,ip,localIp):
        route = 0
        if hop  > 255:
            route,hop = divmod(hop,256)
        if not self.routes.has_key(route):
                self.routes[route] = {}
                if localIp:
                    self.routes[route][0] = localIp
        self.routes[route][hop] = ip        

    def detDistance(self,ttl_recv):
        if ttl_recv > 128:
            return 255 - ttl_recv
        elif ttl_recv <= 64:
            return 64 - ttl_recv
        else:
            return 128 - ttl_recv

def cleanRoute(route):
    from sendPacket import isValidIp

    #set cursor to last item
    last = route.keys().__reversed__().next()
    at_end = True
    cursors = range(1,last+1)
    cursors.reverse()
        
    for cursor in cursors:
        if not route.has_key(cursor -1):
            #route[cursor-1] = "unknown_%s.%d"%(nodeId,cursor-1)
            #we replace this line to link a unknown step to the following step.
            if isValidIp( route[cursor] ): 
                route[cursor-1] = "unknown_%s.%d"%(route[cursor],cursor-1)
                at_end = False
            else:
                route[cursor-1] = route[cursor]
                #route.pop(cursor)
                at_end = False
        elif (route[cursor] == route[cursor-1] and at_end):
            #we have 2 times same ip in route at the end delete last
            route.pop(cursor)
        else:
            #We have an existing hop before this one and it is not similar to next hop
            at_end = False
    return(route)

def uniq(alist):    # Fastest without order preserving
    set = {}
    map(set.__setitem__, alist, [])
    return set.keys()

