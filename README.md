Graphical Traceroute 
====================

based on Impacket / Palea sources

In order to map a bigger network segment quite fast we could set all ICMP packets on the line in the same time and 'guess' the TTL on forehand (keep it high). Based on unique remarkts in the packets we would be able to determine which reply is from whom.

Additionally it might be usefull to be able to write plugins for each node (nsloopup for example, or limited nmap? )
The results are saved in a .dot file that can in turn be parsed into png (or something else).

It's quite simple and unelegant code. Rather a script than a program. Cleanups, smart plugins etc are welcome!

Usage:

	nmap -PN -n -sL 8.8.8.8/24 | grep Host | cut -d ' ' -f2 > test.ips
	sudo ./netmap.py -i IPLIST.txtdot -T
	dot -Tpng filename.dot -o outfile.png
