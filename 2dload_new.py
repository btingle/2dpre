import argparse
import sys, os
import subprocess
import tarfile

BINDIR = os.path.dirname(sys.argv[0])

modes = [
    "upload",
    "export",
    "wipe"
]

def call_psql(db_port, cmd=None, psqlfile=None, vars={}, getdata=False, rethandle=False):
    psql = ["psql", "-p", str(db_port), "-d", "tin", "-U", "tinuser", "--csv"]
    
    for vname, vval in zip(vars.keys(), vars.values()):
        psql += ["--set={}={}".format(vname, vval)]
        
    if psqlfile:
        psql += ["-f", psqlfile]
    else:
        psql += ["-c", cmd]

    if getdata:
        with subprocess.Popen(psql, stdout=subprocess.PIPE) as psql_p:
            data = [r.split(",") for r in psql_p.stdout.readlines()]
            return data
    elif rethandle:
        return subprocess.Popen(psql, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        subprocess.call(psql)
        return None

def check_patched(db_port):
    srcdir = "/local2/load"
    for partition in os.listdir(srcdir):
        ppath = "/".join([srcdir, partition])
        if os.path.isfile(ppath + "/.port"):
            with open(ppath + "/.port") as portf:
                try:
                    thisport = int(portf.read())
                    if thisport == db_port and os.path.isfile(ppath + "/.patched"):
                        return True, ppath
                    elif thisport == db_port:
                        return False, ppath
                except:
                    continue

    print("assuming this database has already been patched, associated files cannot be found")
    return True, None

def patch_database(db_port, db_path):
    print(db_port, db_path)
    sub_id_annotated = open(db_path + "/sub_id_tranche_id", 'w')
    cc_id_annotated = open(db_path + "/cc_id_tranche_id", 'w')
    #cs_id_annotated = open(db_path + "/cs_id_tranche_id", 'w')
    tranche_info = open(db_path + "/tranche_info", 'w')
    tranche_id = 1

    for tranche in sorted(os.listdir(db_path + "/src")):
        print(tranche)
        if not (tranche[0] == 'H' and (tranche[3] == "P" or tranche[3] == "M")):
            continue
        srcpath = db_path + "/src/" + tranche
        tranche_info.write("{} {}\n".format(tranche, tranche_id))

        p1 = subprocess.Popen(["awk", "-v", "a={}".format(tranche_id), "{print $3 \" \" a}", srcpath + "/substance.txt"], stdout=sub_id_annotated)
        p2 = subprocess.Popen(["awk", "-v", "a={}".format(tranche_id), "{print $2 \" \" a}", srcpath + "/supplier.txt" ], stdout=cc_id_annotated)
        #p3 = subprocess.Popen(["awk", "-v", "a={}".format(tranche_id), "{print $3 \" \" a}", srcpath + "/catalog.txt"  ], stdout=cs_id_annotated)
        p1.wait()
        p2.wait()
        #p3.wait()

        tranche_id += 1

    sub_tot = sup_tot = cat_tot = 0
    with open(db_path + "/src/.len_substance") as sub_tot_f:
        sub_tot = int(sub_tot_f.read())
    with open(db_path + "/src/.len_supplier") as sup_tot_f:
        sup_tot = int(sup_tot_f.read())
    with open(db_path + "/src/.len_catalog") as cat_tot_f:
        cat_tot = int(cat_tot_f.read())

    psqlvars = {
        "tranche_sub_id_f" : sub_id_annotated.name,
        "tranche_cc_id_f" : cc_id_annotated.name,
        #"tranche_cs_id_f" : cs_id_annotated.name,
        "tranche_info_f" : tranche_info.name,
        "sub_tot" : sub_tot,
        "sup_tot" : sup_tot,
        "cat_tot" : cat_tot
    }
    print(psqlvars)
    # here for testing
    return

    call_psql(db_port, psqlfile=BINDIR + "/psql/tin_postgres_patch.pgsql", vars=psqlvars)

try:
    database_port = int(sys.argv[1])
except:
    print("port must be an integer!")
    sys.exit(1)

print(database_port)
patched, dbpath = check_patched(database_port)
if not patched:
    print("this database has not been patched yet, doing so now!")
    patch_database(database_port, dbpath)

chosen_mode = sys.argv[2]

if chosen_mode == "upload":

    source_f = sys.argv[3]
    cat_shortname = sys.argv[4]

    if not os.path.isfile(source_f):
        print("file to upload does not exist!")
        sys.exit(1)
    elif not source_f.endswith(".pre"):
        print("expects a .pre file!")
        sys.exit(1)

    psqlvars = {
        "source_f" : None,
        "sb_count" : 0,
        "cc_count" : 0,
        "cs_count" : 0
    }

    psqlvars["source_f"] = os.environ.get("TEMPDIR") + "/" + str(database_port) + "_upload.txt"
    psqlvars["sb_count"] = int(call_psql(database_port, cmd="select currval('sub_id_seq'", getdata=True)[1][0])
    psqlvars["cc_count"] = int(call_psql(database_port, cmd="select currval('cat_content_id_seq'", getdata=True)[1][0])
    psqlvars["cs_count"] = int(call_psql(database_port, cmd="select currval('cat_sub_itm_id_seq'", getdata=True)[1][0])

    print(psqlvars)

    psql_source_f = open(psqlvars["source_f"], 'w')

    data_catid = call_psql(database_port, cmd="select cat_id from catalog where shortname = '{}'".format(cat_shortname), getdata=True)
    if len(data_catid) == 0:
        data_catid = call_psql(database_port, cmd="insert into catalog(name, shortname, updated) values ('{}', '{}', 'now()') returning cat_id".format(cat_shortname, cat_shortname), getdata=True)
    cat_id = int(data_catid[1][0])

    print("processing file for postgres...")
    with tarfile.open(source_f, mode='r:*') as pre_source:
        for member in pre_source:
            print("processing", member)
            tranchename = member.name
            tranche_id = int(call_psql(database_port, cmd="select tranche_id from tranches where tranche_name = '{}'".format(tranchename), getdata=True)[1][0])

            f = pre_source.extractfile(member)
            for line in f:
                psql_source_f.write(' '.join(line.strip().split() + [str(cat_id), str(tranche_id), '\n']))

    call_psql(database_port, psqlfile=BINDIR + "/psql/tin_revised_copy.pgsql", vars=psqlvars)


    

    
