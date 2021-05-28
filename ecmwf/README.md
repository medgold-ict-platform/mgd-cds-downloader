## How to deploy:

- launch command from root folder: chalice deploy --stage ${stage}


## More info:

This chalice project create two lambda functions, the first is executed every 13th of the month to send requests for downloading ecmwf files from Copernicus Data Store (CDS).
This lambda function enable a cloudwatch rule that is executed every day until all files are downloaded, after the rule is disabled.

The second lambda function is executed every 1st day of the month and check what requests in the dynamoDB table are in pending status.
If there are one or more requests in pending status, one new rule is created (or enabled) and executed every day until all pending requests are in done status, after the rule is disabled.


## Dependencies
This project is dependent on resource:
"filesupdate_table":"dev-medgold-files-update"
"BUCKET_NAME":"data.med-gold.eu"

The dynamodb table is created by:
Terraform module https://bitbucket.org/beetobit/medgold-mods/src/develop/mgd-cds-download-files/

## Required 

- CDS (Copernicus Data Store) account and .cdsapirc file that contains key and url to send api requests.
- cdsapi python library ( in /vendor folder )
