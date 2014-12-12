#!/usr/bin/python

# Version 0.1
# This is POC code to proof that we can send out spoofed packets to arrive on the other end maintaining needed data.
# Ensure a wireshark / tcpdump is listening on the catcher side
# Python and Impacket need to be installed


import socket
import re
import struct
import types
import string
import time

from subprocess import *
import threading

from node import EndNode
from impacket import ImpactDecoder, ImpactPacket

class PingSweep(threading.Thread):
    def __init__(self,conf,endnodeList):
        threading.Thread.__init__(self)
        self.conf = conf
        self.endnodeList = endnodeList

    def run(self):
        conf = self.conf
        endnodeList = self.endnodeList
        iplist = conf['targets']
        for endnodeId in endnodeList:
                time.sleep(conf['delay'])
                SendICMP(endnodeList[endnodeId].targetIp,endnodeId,0,64)

class TraceEndNode(threading.Thread):
    def __init__(self,delay):
        threading.Thread.__init__(self)
        self.delay = delay
        self.endnodes = []

    def addEndNode(self,endnode):
        self.endnodes.append(endnode)

    def run(self):
        if len(self.endnodes) > 0:
            for endnode in self.endnodes:
                for ttl in range(1,(endnode.distance+3)):
                    time.sleep(self.delay)
                    hopnr = ttl + (256 * endnode.times_processed)
                    SendICMP( endnode.targetIp,endnode.endnodeId,hopnr,ttl)

class PingReply:
    def __init__(self, packet):
        # Use ImpactDecoder to reconstruct the packet hierarchy.
        rip = ImpactDecoder.IPDecoder().decode(packet)
        # Extract the ICMP packet from its container (the IP packet).
        ricmp = rip.child()

        self.replyType = ricmp.get_icmp_type()
        self.srcIp = rip.get_ip_src()
        self.dstIp = rip.get_ip_dst()
        self.valid = True
        self.recv_ttl = rip.get_ip_ttl()

        if ricmp.ICMP_ECHOREPLY == self.replyType:
            data = ricmp.get_data_as_string()
            self.endnodeId = socket.ntohs(struct.unpack('H',data[4:6])[0])
            self.hopNr = socket.ntohs(struct.unpack('H',data[6:8])[0])

        elif (ricmp.ICMP_UNREACH == self.replyType) or (ricmp.ICMP_TIMXCEED == self.replyType):
            data = ricmp.get_data_as_string()
            if len(data) < (36-8):
                self.valid = False
                return
            self.endnodeId = socket.ntohs(struct.unpack('H',data[(32-8):(34-8)])[0])
            self.hopNr = socket.ntohs(struct.unpack('H',data[(34-8):(36-8)])[0])

        else:
            self.valid = False


def SendICMP(dstIP,sessionNr,counter,ttl):
    # prepare the IP part
    ip = ImpactPacket.IP()
    ip.set_ip_dst(dstIP)
    #this counter isn't used.
    ip.set_ip_id(counter)
    ip.set_ip_ttl(ttl)

    # prepare the ICMP part
    icmp = ImpactPacket.ICMP()
    #is used to read out uniquenumber in case of DU ICMP reply
    icmp.set_icmp_id(sessionNr)
    #is used to read out sessionnumber in case of DU ICMP reply
    icmp.set_icmp_seq(counter)

    #auto generate checksum
    icmp.set_icmp_cksum(0)
    icmp.auto_checksum = 1
    icmp.set_icmp_type(icmp.ICMP_ECHO)

    # prepare the payload
    # put the target IP and the sequence number in the payload also for later recovery
    data = socket.inet_aton(dstIP)+struct.pack('H',socket.htons(sessionNr))+struct.pack('H',socket.htons(counter))

    # compose the total packet IP / icmp / payload
    icmp.contains(ImpactPacket.Data(data))
    ip.contains(icmp)

    # Open a raw socket. Special permissions are usually required.
    s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)

    # and set it free
    return s.sendto(ip.get_packet(), (dstIP, 0))

def isValidIp(ip):
    pattern = r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
    if re.match(pattern, ip):
        return True
    else:
        return False

def resolveIp(ip):
    name = False
    if isValidIp(ip):
        try:
            name = socket.gethostbyaddr(ip)[0]
        except:
            pass
    if name: return name
    return ip
