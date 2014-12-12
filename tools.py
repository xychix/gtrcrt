#!/usr/bin/env python  
from socket import *   
  
if __name__ == '__main__':  
    print 'Starting scan on host ', targetIP  
 
def portscan(targetIp,ports):
    open = []
    for p in ports:  
        s = socket(AF_INET, SOCK_STREAM)  
        result = s.connect_ex((targetIp, p))  
        if(result == 0) :  
            open.append(p)
        s.close()
    return open
