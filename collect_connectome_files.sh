#!/usr/bin/env bash

# Create a new directory called Connectome_sample_data
if [ ! -d Connectome_sample_data ]; then
  mkdir Connectome_sample_data
fi

# Find CSV files with session name and copy them to the new directory
files=(`find /isilon/datalake/riipl/original/ADRC/3A*/DTI/mrtrix* -maxdepth 1 -type f -name "*.csv"`)
echo "I found ${#files[@]}"

for file in ${files[@]}; do 

    # Extract session name from file path
    session_name=$(dirname "$file" | egrep -o "3[A-Z]+[0-9]+_[0-9]+(_[0-9]+)")

    #
    if [[ -z "$session_name" ]]; then
        session_name=$(dirname "$file" | egrep -o "3[A-Z]+[0-9]+_[0-9]+")
    fi

    if [[ -z "$session_name" ]]; then
        break
    fi
    

    # Copy file with prefix or renamed file using session name
    cp -v "$file" Connectome_sample_data/"$session_name"_"`basename $file`"
done