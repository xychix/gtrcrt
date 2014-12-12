import time

class TimeLog:
    def __init__(self):
        self.logs = {}
        self.loglist = []
        self.log() 
    
    def log(self,name=None):
        if name == 'main':
            raise NameError, "'main' is a reserved TimeLog"
        else:
            if name == None:
                name = 'main'
            if not self.logs.has_key(name):
                self.logs[name] = []
                self.loglist.append(name)
            self.logs[name].append(time.time())

    def runtime(self,name=None):
        if name == None:
            name = 'main'
        return (self.logs[name][-1] - self.logs[name][0])
    
    def report(self):
        for log in self.loglist:
            print "\ttimer %s ran for %s seconds"%(log, round(self.runtime(log),3))
