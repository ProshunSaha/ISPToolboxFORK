## DO NOT USE FOR PRODUCTION - only for integration testing

# purge tasks before starting new one
python3 -m celery -A webserver purge -f

# Test site customize
echo "import coverage" >  /opt/conda/lib/python3.8/site-packages/sitecustomize.py
echo "coverage.process_startup()" >>  /opt/conda/lib/python3.8/site-packages/sitecustomize.py

exec python3 -m celery worker --beat -A webserver --loglevel=info --pool=solo