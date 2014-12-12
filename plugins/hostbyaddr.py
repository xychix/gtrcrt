import socket
import re

# this function should have a .audience()
# the main app will use this to determine for what ip's the 'work' should be started
def audience():
    ''' the audience function in a plugin will be called before we pass ip's and ipClasses to this plugin
        it is used to determine what ip's whould be passed to the work() function.
        ['all','endpoint','router'] are the options at this moment

        default is all, os if this function does not exist or returns an expected value the 'work' function
        will be started for all ip's
    '''
    return ('all')

def name():
    return('Reverse DNS')

def work(ip, ipclass):
    ''' The work() is going to do all the heavy work. it will be called from a threaded model so make sure
        not to write code blocking a I/O object that would be needed by the other threads running this
        function.

        In this specific example we're do a reverselookup for the ip to display a hostname
    '''
    name = 'no reverse'
    if isValidIp(ip):
        try:
            name = socket.gethostbyaddr(ip)[0]
        except:
            pass
    return name


# functions used in this plugin
def isValidIp(ip):
    ''' This is a simple regexp to ensure we're only looking up this that appear to be valid ip's
    '''
    pattern = r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
    if re.match(pattern, ip):
        return True
    else:
        return False

