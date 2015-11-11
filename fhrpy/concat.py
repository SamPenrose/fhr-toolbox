#!/usr/bin/env python
import healthreportutils

import mrjob
from mrjob.job import MRJob

@healthreportutils.FHRMapper()
def map(job, key, payload):
    '''
    Iterate over $data
    '''
    yield ('1', key, payload)


def reduce(job, k, vlist):
    yield list(vlist)

class AggJob(MRJob):
    HADOOP_INPUT_FORMAT="org.apache.hadoop.mapred.SequenceFileAsTextInputFormat"
    HADOOP_OUTPUT_FORMAT="org.apache.hadoop.mapred.SequenceFileOutputFormat"
    INPUT_PROTOCOL = mrjob.protocol.RawProtocol

    def run_job(self):
        # Do the big work
        super(AggJob, self).run_job()

    def mapper(self, key, value):
        return map(self, key, value)

    def reducer(self, key, vlist):
        return reduce(self, key, vlist)


if __name__ == '__main__':
    AggJob.run()
