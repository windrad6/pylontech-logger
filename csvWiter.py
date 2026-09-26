import csv, datetime, os
import numbers


class csvWriter:
    def __init__(self, path : str, name : str, delimiter : int = ",", flushLines : int = 1):
        self.path = path
        self.name = name
        self.headerList = []
        self.delimiter = delimiter
        self.flushLines = flushLines
        self.linesWritten = 0
        self.fh = None
        self.fname = ""
        self.lastLineUpdateDay = None
        self.writer = None

    def setHeader(self, headerList : list):
        self.headerList = headerList

    def buildFName(self):
        now = datetime.date.today() 
        self.fname = f"{now.year}_{now.month}_{now.day}_{self.name}.csv"

    def isDayChange(self):
        now = datetime.date.today() 
        if now.day != self.lastLineUpdateDay:
            return True
        return False

    def formatElm(self, data):
        if isinstance(data, numbers.Number):
            return "{0:.4f}".format(data)
        return data
        

    def writeLine(self, dataList : list):

        dataList[:] = [self.formatElm(elm) for elm in dataList]

        if self.fh is not None and self.isDayChange():
            self.fh.close()
            self.fh = None

        if self.fh is None:
            self.buildFName()
            os.makedirs(self.path, exist_ok=True)
            fileExists = False
            if os.path.isfile(f"{self.path}/{self.fname}"):
                fileExists = True
            else:
                print(f"Create new file {self.path}/{self.fname}")
            self.fh = open(f"{self.path}/{self.fname}", 'a')
            self.writer = csv.writer(self.fh, delimiter = self.delimiter)
            if len(self.headerList) > 0 and not fileExists:
                self.writer.writerow(self.headerList)

        self.writer.writerow(dataList)
        self.linesWritten = self.linesWritten + 1
        if self.linesWritten >= self.flushLines:
            self.fh.flush()
            self.linesWritten = 0
        self.lastLineUpdateDay = datetime.date.today().day 

    