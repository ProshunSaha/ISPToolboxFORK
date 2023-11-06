#!/bin/bash
# (c) Meta Platforms, Inc. and affiliates. Copyright
set -e
BASEDIR=$(dirname "$0")

LAMBDA_FUNC_NAME="celery_monitoring"
echo "Zipping Lambda Oncall"
rm -rf src/node_modules/
cd $BASEDIR/src/; npm install --only=prod; cd -
rm -f function.zip
cd $BASEDIR/src/; zip -r ../function.zip *; cd -
echo "Updating Lambda function $LAMBDA_FUNC_NAME"
echo "fileb://$BASEDIR/function.zip"
aws lambda update-function-code --region us-west-1 \
--function-name $LAMBDA_FUNC_NAME --zip-file fileb://$BASEDIR/function.zip
