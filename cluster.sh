#!/bin/bash

# WARNNING: this script is not fully tested, you are on your own risk while using it.

# Script:               cluster.sh
# Function:             Set and unset TurboCRM clusters
# Author:               lenin <lenin.lee@gmail.com>
# Begin:                2010-11-27 13:18:26 Saturday
# Build:                2010-12-01 11:48:05 Wednesday

dirs='storage page temp rpool spool search/index code/www/datacache code/www/rptdata code/www/tmpfile'

helpcluster()
{
    echo 'TurboCRM Cluster Helper Script by Lenin <lenin.lee@gmail.com>'
    echo 'WARNNING: this script is not fully tested, you are on your own risk while using it.'
    echo
    echo 'Usage: cluster.sh -m [filesvr|backbone|slave|backup|restore] [OPTIONS]'
    echo
    echo 'Examples:'
    echo '      1. On file server:'
    echo '          cluster.sh -m filesvr -d /opt/crmdata -s crmsvr01:192.168.1.6,crmsvr02:192.168.1.9'
    echo '      2. On backbone server:'
    echo '          cluster.sh -m backbone -d nfssvr01:/opt/crmdata -s nfssvr01:192.168.1.1 -e'
    echo '      3. On slave server:'
    echo '          cluster.sh -m slave -d nfssvr01:/opt/crmdata -s nfssvr01:192.168.1.1 -b 192.168.1.6 -e'
    echo '      4. Use the backbone server as file server at the same time:'
    echo '          cluster.sh -m filesvr -d /opt/turbocrm -s crmsvr02:192.168.1.9'
    echo '      5. Use the slave server as file server at the same time:'
    echo '          cluster.sh -m filesvr -d /opt/turbocrm -s crmsvr01:192.168.1.6 -b 192.168.1.6'
    echo '      6. Backup cluster files:'
    echo '          cluster.sh -m backup -o /root/crm_cluster_backup'
    echo '      7. Restore backup files:'
    echo '          cluster.sh -m restore -i /root/crm_cluster_backup'
    echo
    echo 'Options:'
    echo '      -h:             Show this message.'
    echo '      -m [MODE]:      Working mode, must be specified.'
    echo '                      Modes:'
    echo '                          filesvr:    File server mode.'
    echo '                          backbone:   Use this value in the main CRM server, one cluster should only have one main server.'
    echo '                          slave:      Use this value in the less important CRM servers.'
    echo '                          backup:     Backup files of system and TurboCRM which will be affected by cluster configuration.'
    echo '                          restore:    Restore files from a backup copy.'
    echo '      -d [DIR]:       Specify the directory in which the shared folders to be created.'
    echo '                          This option should be used only when the value of option -m is filesvr.'
    echo '      -b [IP]:        IP address of the backbone server, this option only has sense in slave mode.'
    echo '      -e:             Empty all those directories which are to be mounted to NFS ones, backbone and slave modes only.'
    echo '      -i [DIR]:       Used in restore mode, copy files from the given directory.'
    echo '      -o [DIR]:       Used in backup mode, copy files to a given directory.'
    echo '      -s [PAIRS]:     Specify ip addresses and hostnames of CRM servers, the format is:'
    echo '                          hostname1:ip1,hostname2:ip2,...'
    exit 0
}
complain()
{
    echo "$@" >&2
}
checkmode()
{
    if [ $# -eq 1 ]; then
        if [ "$1" == 'filesvr' -o "$1" == 'backbone' -o "$1" == 'slave' -o "$1" == 'backup' -o "$1" == 'restore' ]; then
            return 0
        fi
    fi
    return 1
}
makenfsdirs()
{
    if ! [ -z $nfsdir ]; then
        for dir in $dirs; do
            if ! mkdir -p "${nfsdir}/${dir}" > /dev/null 2>&1; then
                return 1
            fi
        done
        chmod -R 777 $nfsdir
    fi
    return 0
}
exporthost()
{
    if [ $# -eq 2 ]; then
        if grep $1 /etc/hosts > /dev/null 2>&1; then
            if sed -i "s/^${1}\s\+.*$/${1} ${2} ${2}/" /etc/hosts > /dev/null 2>&1; then
                return 0
            fi
        else
            if sed -i "\$a\\${1} ${2} ${2}" /etc/hosts > /dev/null 2>&1; then
                return 0
            fi
        fi
    fi
    return 1
}
exporthosts()
{
    if [ ${#hosts[@]} -ne ${#ips[@]} ]; then
        complain 'Error: Hostnames do not match IP addresses.'
        return 1
    fi

    if [ ${#hosts[@]} -eq 0 ]; then
        return 0
    fi

    for (( i=0; i<${#ips[@]}; i++)); do
        if ! exporthost ${ips[$i]} ${hosts[$i]}; then
            return 1
        fi
    done

    return 0
}
exportdir()
{
    if [ $# -ge 2 ]; then
        local dir=$1
        shift
        local line="${dir}"
        local count=$#
        for (( i=0; i<$count; i++ )); do
            line="${line} $1(rw,no_root_squash)"
            shift
        done

        touch /etc/exports

        if grep $dir /etc/exports > /dev/null 2>&1; then
            sed -i "s#^${dir}\s\+.*\$#${line}#" /etc/exports
        else
            echo "${line}" >> /etc/exports
        fi
        return 0
    fi
    return 1
}
exportdirs()
{
    if [ -z $nfsdir ] || [ ${#hosts[@]} -eq 0 ]; then
        return 0
    fi

    for dir in $dirs; do
        local path="${nfsdir}/${dir}"
        if ! exportdir $path ${hosts[@]}; then
            return 1
        fi
    done

    return 0
}
restartnfs()
{
    if grep CentOS /etc/issue > /dev/null 2>&1; then
        chkconfig --level 2345 nfs on
        service nfs restart
    fi
    return 0
}
addmountpoint()
{
    if [ $# -eq 2 ]; then
        if grep $1 /etc/fstab > /dev/null 2>&1; then
            sed -i "s#^.*\\s\+$1.*\$#$2 $1 nfs defaults 0 0#" /etc/fstab
        else
            sed -i "\$a\\$2 $1 nfs defaults 0 0" /etc/fstab
        fi
        return 0
    fi
    return 1
}
addmountpoints()
{
    if [ -z $nfsdir ] || [ ${#dirs[@]} -eq 0 ]; then
        return 0
    fi

    for dir in $dirs; do
        path="/opt/turbocrm/$dir"
        if ! addmountpoint $path "${nfsdir}/$dir"; then
            return 1
        fi
    done
    return 0
}
syncnfsdirs()
{
    if [ -z $nfsdir ] || [ ${#dirs[@]} -eq 0 ]; then
        return 0
    fi

    for dir in $dirs; do
        path="/opt/turbocrm/$dir"
        nfspath=`dirname ${nfsdir}/${dir}`
        if ! rsync -arvz "${path}" "${nfspath}"; then
            return 1
        fi
    done
    return 0
}
disablecomponent()
{
    if [ $# -ne 1 ]; then
        complain 'Error: Give the component name as the only parameter.'
        return 1
    fi

    if ! sed -i "/^result=.*${1}.*\$/a\\result=1" /opt/turbocrm/tsvr/start.sh > /dev/null 2>&1; then
        echo "Error: Cannot stop service $1."
        exit 1
    fi

    return 0
}
redirectsearchserver()
{
    if ! [ -z $backbone ]; then
        if ! sed -i "s#^SearchServer.*\$#SearchServer=${backbone};#" /opt/turbocrm/tsvr/turbocrm.ini > /dev/null 2>&1; then
            complain 'Error: Cannot point search server.'
            exit 1
        fi
    fi
    return 0
}
isrunning()
{
    local cmd="ps -ef"
    local orglen=${#cmd}
    local amt=0
    while [ $# -gt 0 ]; do
        cmd="${cmd}|grep $1"
        shift
    done

    if [ ${#cmd} -gt $orglen ]; then
        cmd="${cmd}|grep -v grep|wc -l"
        amt=`eval $cmd`
        if [ $amt -gt 0 ]; then
            return 0
        else
            return 1
        fi
    fi
    return 0
}
iscrmrunning()
{
    if isrunning turbocrm ddsvr || isrunning turbocrm bgtasksvr || isrunning turbocrm httpd; then
        return 0
    fi
    return 1
}
checkoptions()
{
    # -m must be given
    if [ -z $mode ]; then
        complain 'Error: -m must be specified.'
        return 1
    fi
    if ! checkmode $mode; then
        complain 'Error: Unknown mode.'
        return 1
    fi

    # output directory must exists in backup mode
    if ! [ -z $output ] && ! [ -d $output ]; then
        complain 'Error: Output directory does not exist.'
        return 1
    fi

    # Check hosts and ips
    if [ ${#hosts[@]} -ne ${#ips[@]} ]; then
        complain 'Error: -s option has been given an invalid string.'
        return 1
    fi

    # -s, -d should only be used in filesvr, backbone and slave modes
    if [ "$mode" != 'filesvr' -a "$mode" != 'backbone' -a "$mode" != 'slave' ]; then
        if [ ${#hosts[@]} -gt 0 ]; then
            complain 'Error: -s is only available in filesvr, backbone and slave modes.'
            return 1
        fi
        if ! [ -z $nfsdir ]; then
            complain 'Error: -d is only available in filesvr, backbone and slave modes.'
            return 1
        fi
    fi

    # -b should only be used in filesvr and slave modes
    if [ "$mode" != 'filesvr' -a "$mode" != 'slave' ] && ! [ -z $backbone ]; then
        complain 'Error: -b is only available in filesvr and slave modes.'
        return 1
    fi

    # -e should only be used in backbone and slave mode
    if [ "$mode" != 'backbone' -a "$mode" != 'slave' -a $empty -eq 1 ]; then
        complain 'Error: -e is only available in backbone and slave modes.'
        return 1
    fi

    # -o should only be used in backup mode
    if [ "$mode" != 'backup' ] && ! [ -z $output ]; then
        complain 'Error: -o is only available in backup mode.'
        return 1
    fi
    if [ "$mode" == 'backup' ]; then
        if [ -z $output ]; then
            complain 'Error: Missing backup directory.'
            return 1
        fi
        if ! [ -d $output ]; then
            complain 'Error: Invalid backup directory.'
            return 1
        fi
    fi

    # -i should only be used in restore mode
    if [ "$mode" != 'restore' ] && ! [ -z $input ]; then
        complain 'Error: -i is only available in restore mode.'
        return 1
    fi
    if [ "$mode" == 'restore' ]; then
        if [ -z $input ]; then
            complain 'Error: Missing backup directory.'
            return 1
        fi
        if ! [ -d $input ]; then
            complain 'Error: Invalid backup directory.'
            return 1
        fi
    fi

    return 0
}
checkenv()
{
    # TurboCRM must be stopped first
    if iscrmrunning; then
        echo 'TurboCRM must be stopped first.'
        return 1
    fi

    return 0
}

# Options
declare -a hosts
declare -a ips
empty=0
asslave=0
mode=''
nfsdir=''
backbone=''
output=''
input=''
while getopts 'hei:m:b:d:o:s:' OPT; do
    case $OPT in
        b)
            backbone=$OPTARG
            asslave=1
            ;;
        d)
            nfsdir=$OPTARG
            ;;
        e)
            # This option may delete files on file server, so currently disabled.
            empty=0
            ;;
        i)
            input=$OPTARG
            ;;
        m)
            mode=$OPTARG
            ;;
        o)
            output=$OPTARG
            ;;
        s)
            tmp=(`echo $OPTARG|tr ',' ' '`)
            i=0
            for raw in ${tmp[@]}; do
                arr=(${raw//:/ })
                hosts[$i]=${arr[0]}
                ips[$i]=${arr[1]}
                i=$i+1
            done
            ;;
        h)
            helpcluster
            ;;
    esac
done

if ! checkenv; then
    exit 1
fi

if ! checkoptions; then
    echo 'Use option -h to help yourself .'
    exit 1
fi

# Try to export hosts
if ! exporthosts; then
    complain 'Error: Cannot export hosts.'
    exit 1
fi

# Disable TEmailServer and SearchServer on slaves
if [ "$mode" == 'slave' ] || [ "$mode" == 'filesvr' -a $asslave -eq 1 ]; then
    if ! disablecomponent TEmailServer; then
        complain 'Error: Cannot disable TEmailServer.'
        exit 1
    fi
    if ! disablecomponent SearchServer; then
        complain 'Error: Cannot disable SearchServer.'
        exit 1
    fi
    if ! redirectsearchserver; then
        complain 'Error: Cannot redirect SearchServer.'
        exit 1
    fi
fi

case $mode in
    'filesvr')
        # Try to make NFS direstories
        if ! makenfsdirs; then
            complain 'Error: Cannot make NFS directories.'
            exit 1
        fi
        # Export directories
        if ! exportdirs; then
            complain 'Error: Cannot export directories.'
            exit 1
        fi
        # Restart NFS service
        restartnfs
        ;;
    'backbone'|'slave')
        # Add NFS directories to /etc/fstab if option -d is given
        if ! addmountpoints; then
            complain 'Error: Cannot create mount points.'
            exit 1
        fi
        # Synchronize local directories with the NFS ones if option -d is given
        if ! syncnfsdirs; then
            complain 'Error: Cannot synchronize directories.'
            exit 1
        fi
        # Empty all local directories which are to be mounted to NFS ones if option -e is given
        if [ $empty -eq 1 ]; then
            umount -a > /dev/null 2>&1
            rm -rf /opt/turbocrm/storage/* > /dev/null 2>&1
            rm -rf /opt/turbocrm/page/* > /dev/null 2>&1
            rm -rf /opt/turbocrm/rpool/* > /dev/null 2>&1
            rm -rf /opt/turbocrm/spool/* > /dev/null 2>&1
            rm -rf /opt/turbocrm/temp/* > /dev/null 2>&1
            rm -rf /opt/turbocrm/code/www/datacache/* > /dev/null 2>&1
            rm -rf /opt/turbocrm/code/www/tmpfile/* > /dev/null 2>&1
            rm -rf /opt/turbocrm/code/www/rptdata/* > /dev/null 2>&1
            rm -rf /opt/turbocrm/search/index/* > /dev/null 2>&1
        fi
        # Mount NFS directories if option -d is given
        if ! [ -z $nfsdir ]; then
            umount -a > /dev/null 2>&1
            mount -a > /dev/null 2>&1
        fi
        ;;
    'backup')
        cp -af /etc/fstab $output
        cp -af /etc/exports $output
        cp -af /etc/hosts $output
        cp -af /opt/turbocrm/tsvr/turbocrm.ini $output
        cp -af /opt/turbocrm/tsvr/start.sh $output
        ;;
    'restore')
        cp -af "$input/fstab" /etc/fstab
        cp -af "$input/exports" /etc/exports
        cp -af "$input/hosts" /etc/hosts
        cp -af "$input/turbocrm.ini" /opt/turbocrm/tsvr/turbocrm.ini
        cp -af "$input/start.sh" /opt/turbocrm/tsvr/start.sh
        ;;
esac

echo 'Job done !'
exit 0
