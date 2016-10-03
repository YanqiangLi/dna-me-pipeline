#!/usr/bin/env python
# coding: utf-8
# test-py-parallel 0.0.1
# Generated by dx-app-wizard.
#
# Scatter-process-gather execution pattern: Your app will split its
# input into multiple pieces, each of which will be processed in
# parallel, after which they are gathered together in some final
# output.
#
# This pattern is very similar to the "parallelized" template.  What
# it does differently is that it formally breaks out the "scatter"
# phase as a separate black-box entry point in the app.  (As a side
# effect, this requires a "map" entry point to call "process" on each
# of the results from the "scatter" phase.)
#
# Note that you can also replace any entry point in this execution
# pattern with an API call to run a separate app or applet.
#
# The following is a Unicode art picture of the flow of execution.
# Each box is an entry point, and vertical lines indicate that the
# entry point connected at the top of the line calls the entry point
# connected at the bottom of the line.  The letters represent the
# different stages in which the input is transformed, e.g. the output
# of the "scatter" entry point ("array:B") is given to the "map" entry
# point as input.  The "map" entry point calls as many "process" entry
# points as there are elements in its array input and gathers the
# results in its array output.
#
#          ┌──────┐
#       A->│ main │->D (output from "postprocess")
#          └┬─┬─┬─┘
#           │ │ │
#          ┌┴──────┐
#       A->│scatter│->array:B
#          └───────┘
#             │ │
#            ┌┴──────────────┐
#   array:B->│      map      │->array:C
#            └─────────┬─┬─┬─┘
#               │      │ . .
#               │     ┌┴──────┐
#               │  B->│process│->C
#               │     └───────┘
#            ┌──┴────────┐
#   array:C->│postprocess│->D
#            └───────────┘
#
# A = original app input, split up by "scatter" into pieces of type B
# B = an input that will be provided to a "process" entry point
# C = the output of a "process" entry point
# D = app output aggregated from the outputs of the "process" entry points
#
# See https://wiki.dnanexus.com/Developer-Portal for documentation and
# tutorials on how to modify this file.
#
# DNAnexus Python Bindings (dxpy) documentation:
#   http://autodoc.dnanexus.com/bindings/python/current/

import os
import dxpy
import subprocess
import shlex
import glob
import logging

DEBUG = True

logger = logging.getLogger(__name__)
logger.addHandler(dxpy.DXLogHandler())
logger.propagate = False

if DEBUG:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)


STRIP_EXTENSIONS = ['.gz', '.fq', '.fastq', '.fa', '.fasta']


def strip_extensions(filename, extensions):
    basename = filename
    for extension in extensions:
        basename = basename.rpartition(extension)[0] or basename
    return basename


@dxpy.entry_point("postprocess")
def postprocess(bam_files, report_files, bam_root, nthreads=8, use_cat=False, use_sort=False):
    # This is the "gather" phase which aggregates and performs any
    # additional computation after the "map" (and therefore after all
    # the "process") jobs are done.

    if DEBUG:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    logger.debug("* In Postprocess - refactoed dme-merge-bams - *")

    fnames = []
    for bam in bam_files:
        dxbam = dxpy.DXFile(bam)
        dxfn = dxbam.describe()['name']
        logger.info("* Downloading %s... *" % dxfn)
        dxpy.download_dxfile(bam, )
        fnames.append(bam_root + '_bismark_techrep.bam')

    outfile_name = bam_root
    logger.info("* Merged alignments file will be: %s *" % outfile_name + '.bam')
    if len(fnames) == 1:
        rep_outfile_name = bam_root + '_bismark_biorep'
        os.rename('sofar.bam', rep_outfile_name + '.bam')
        logger.info("* Only one input file, no merging required.")

    else:
        if use_cat:
            for fn in fnames:
                if not os.path.isfile('sofar.bam'):
                    os.rename(fn, 'sofar.bam')
                else:
                    logger.info("* Merging...")
                    # NOTE: keeps the first header
                    catout = subprocess.check_output('samtools cat sofar.bam %s > merging.bam' % fn)
                    logger.info(catout)
                    os.rename('merging.bam', 'sofar.bam')

            # At this point there is a 'sofar.bam' with one or more input bams

            logger.info("* Files merged into %s (via cat) *" % outfile_name + '.bam')

        else:
            # use samtools merge
            filelist = " ".join(fnames)
            logger.info("Merging via merge %s " % filelist)
            mergeout = subprocess.check_output('samtools merge -nf %s %s' % ('merging.bam', filelist))
            logger.info(mergeout)

        if use_sort:
            # sorting needed due to samtools cat
            logger.info("* Sorting merged bam...")
            sortout = subprocess.check_output(['samtools sort -@', nthreads, '-m 6G -f sofar.bam sorted.bam'])
            logger.info(sortout)
            os.rename('sorted.bam', outfile_name + '.bam')
        else:
            os.rename('sofar.bam', outfile_name + '.bam')



    output = {
        "bam_techrep": dxpy.dxlink(myfiles[0]),
        "bam_techrep_qc": dxpy.dxlink(myfiles[1]),
        "map_techrep": dxpy.dxlink(myfiles[2]),
        "reads": "2888888",
        "metadata": '{ "Some": "Stuff"}'
    }
    return output

@dxpy.entry_point("process")
def process(scattered_input, dme_ix, ncpus, reads_root):
    # Fill in code here to process the input and create output.

    if DEBUG:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    dme_ix = dxpy.DXFile(dme_ix)

    # The following line(s) download your file inputs to the local file system
    # using variable names for the filenames.

    dxpy.download_dxfile(dme_ix.get_id(), "index.tgz")
    fq = dxpy.DXFile(scattered_input)
    name = fq.describe()['name']
    dxpy.download_dxfile(fq.get_id(), name)
    bam_root = name + '_techrep'

    logger.info("* === Calling DNAnexus and ENCODE independent script... ===")
    logger.debug('command line: dname_align_se.sh index.tgz %s %d %s' % (name, ncpus, bam_root))
    subprocess.check_call('/usr/bin/dname_align_se.sh index.tgz %s %d %s' % (name, ncpus, bam_root))
    logger.info("* === Returned from dnanexus post align ===")

    # As always, you can choose not to return output if the
    # "postprocess" stage does not require any input, e.g. rows have
    # been added to a GTable that has been created in advance.  Just
    # make sure that the "postprocess" job does not run until all
    # "process" jobs have finished by making it wait for "map" to
    # finish using the depends_on argument (this is already done for
    # you in the invocation of the "postprocess" job in "main").

    os.rename(name, bam_root+'.bam')
    return {
        "bam_file": dxpy.dxlink(dxpy.upload_local_file(bam_root+'.bam')),
        "report_file": dxpy.dxlink(dxpy.upload_local_file(bam_root+'.report'))
    }


@dxpy.entry_point("map")
def map_entry_point(array_of_scattered_input, process_input):
    # The following calls "process" for each of the items in
    # *array_of_scattered_input*, using as input the item in the
    # array, as well as the rest of the fields in *process_input*.
    if DEBUG:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    logger.debug("* in map entry point with %s *" % process_input)
    process_jobs = []
    for item in array_of_scattered_input:
        logger.debug("* scattering: %s *" % item)
        process_input["scattered_input"] = item
        process_jobs.append(dxpy.new_dxjob(fn_input=process_input, fn_name="process"))

    bams = []
    reports = []
    for subjob in process_jobs():
        bams.append(subjob.get_output_ref('bam_file'))
        reports.append(subjob.get_output_ref('report_file'))

    return {
        "bam_files": bams,
        "report_files": reports,
    }


@dxpy.entry_point("scatter")
def scatter(orig_reads, split_size):
    # Fill in code here to do whatever is necessary to scatter the
    # input.
    if DEBUG:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    splitsize = split_size * 1000000 * 4
    # each FQ read is 4 lines
    os.mkdir('splits')

    for f in orig_reads:
        reads_filename = dxpy.describe(f)['name']
        reads_basename = strip_extensions(reads_filename, STRIP_EXTENSIONS)
        dxpy.download_dxfile(dxpy.DXFile(f).get_id(), reads_filename)

        reads_root_name = simplify_name() or reads_basename

        subprocess.check_call('/bin/zcat %s | /usr/bin/split -l %d -d - %s ' % (reads_filename, splitsize, 'splits/' + reads_root_name), shell=True)

    splits = os.listdir('splits')
    logger.info("* Return from scatter: %s *" % splits)

    # SHould we gzip here?
    return {
        "reads_root_name": reads_root_name,
        "array_of_scattered_input": [ 
            dxpy.dxlink(dxpy.upload_local_file('splits/' + split_file)) for split_file in splits]
        }


def simplify_name():
    # Try to simplify the names

    rep_root = ''
    if os.path.isfile('/usr/bin/parse_property.py'):
        rep_root = subprocess.check_output(['parse_property.py', '--job', os.environ['DX_JOB_ID'],'--root_name', '--quiet'], shell=True)

    return rep_root


@dxpy.entry_point("main")
def main(reads, dme_ix, ncpus, splitsize):

    # The following line(s) initialize your data object inputs on the platform
    # into dxpy.DXDataObject instances that you can start using immediately.

    #dx_reads = [dxpy.DXFile(item) for item in reads]

    # The following line(s) download your file inputs to the local file system
    # using variable names for the filenames.



    # We first create the "scatter" job which will scatter some input
    # (replace with your own input as necessary).
    logger.debug("* Start Scatter with %d files %sM read splits *" % (len(reads), splitsize))

    scatter_job = dxpy.new_dxjob(fn_input={
                                 'orig_reads': reads,
                                 'split_size': splitsize,
                                 },
                                 fn_name="scatter")

    # We will want to call "process" on each output of "scatter", so
    # we call the "map" entry point to do so.  We can also provide
    # here additional input that we want each "process" entry point to
    # receive, e.g. a GTable ID to which the "process" function should
    # add rows of data.
    reads_root = scatter_job.get_output_ref("reads_root_name")
    map_input = {
        "array_of_scattered_input": scatter_job.get_output_ref("array_of_scattered_input"),
        "process_input": {
            "reads_root": reads_root,
            "ncpus": ncpus,
            "dme_ix": dme_ix
            }
        }
    logger.debug("* Start Map with: %s *" % map_input)
    map_job = dxpy.new_dxjob(fn_input=map_input, fn_name="map")

    # Finally, we want the "postprocess" job to run after "map" is
    # done calling "process" on each of its inputs.  Note that a job
    # is marked as "done" only after all of its child jobs are also
    # marked "done".
    postprocess_input = {
        "bam_files": map_job.get_output_ref("bam_files"),
        "report_files": map_job.get_output_ref("report_files"),
        "bam_root": reads_root + '_techrep'
        }
    logger.debug("* Start Post process with: %s *" % postprocess_input)
    postprocess_job = dxpy.new_dxjob(fn_input=postprocess_input,
                                     fn_name="postprocess",
                                     depends_on=[map_job])

    # If you would like to include any of the output fields from the
    # postprocess_job as the output of your app, you should return it
    # here using a job-based object reference.
    #
    # return { "app_output_field": postprocess_job.get_output_ref("final_output"), ...}
    #
    # Tip: you can include in your output at this point any open
    # objects (such as gtables) which will be closed by a job that
    # finishes later.  The system will check to make sure that the
    # output object is closed and will attempt to clone it out as
    # output into the parent container only after all subjobs have
    # finished.

    output = {}
    output["bam_techrep"] = dxpy.dxlink(postprocess_job.get_output_ref("bam_techrep"))
    output["bam_techrep_qc"] = dxpy.dxlink(postprocess_job.get_output_ref("bam_techrep_qc"))
    output["map_techrep"] = dxpy.dxlink(postprocess_job.get_output_ref("map_techrep"))
    output["reads"] = postprocess_job.get_output_ref("reads")
    output["metadata"] = postprocess_job.get_output_ref("metadata")

    return output

dxpy.run()
