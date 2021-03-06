#!/bin/bash
# in: TRANCHES, PARTITION_ID, CATALOG_SHORTNAME
PARTITION_ID=$1
TRANCHES=$2
CATALOG=$3
EXPORT_DEST=${EXPORT_DEST-/nfs/exb/zinc22/2dpre_results/$CATALOG}

BINPATH=$(dirname $0)
BINPATH=${BINPATH-.}
export BINPATH
export CATALOG

mkdir -p $EXPORT_DEST
EXPORT_DEST=$EXPORT_DEST
p_start=$(grep -w $PARTITION_ID $BINPATH/partitions.txt | awk '{print $1}')
p_end=$(grep -w $PARTITION_ID $BINPATH/partitions.txt | awk '{print $2}')
tranche_files=$(python $BINPATH/get_partition_tranche_files.py $TRANCHES $p_start $p_end)

for tranche_file in $tranche_files; do
    if [[ $tranche_file == MISSING* ]]; then
        hlogp=$(printf $tranche_file | cut -d':' -f2)
        echo $hlogp missing from tranches, no worries
        touch $EXPORT_DEST/$hlogp
	tar -C $EXPORT_DEST -rf $EXPORT_DEST/$PARTITION_ID.pre $hlogp
	continue
    fi
    echo $tranche_file
    TRANCHE_NAME=$(basename $tranche_file | cut -d'.' -f1)
    export INPUT_FILE=$tranche_file
    export OUTPUT_DEST=$EXPORT_DEST/$TRANCHE_NAME
    if [ -f $OUTPUT_DEST ]; then
	intarfile=$(tar tf $EXPORT_DEST/$PARTITION_ID.pre | grep $TRANCHE_NAME)
	if [ -z "$intarfile" ]; then
		tar -C $EXPORT_DEST -rf $EXPORT_DEST/$PARTITION_ID.pre $TRANCHE_NAME
	else
        	continue
	fi
    fi
    $BINPATH/pre_process_file.bash
    tar -C $EXPORT_DEST -rf $EXPORT_DEST/$PARTITION_ID.pre $TRANCHE_NAME
    
done
