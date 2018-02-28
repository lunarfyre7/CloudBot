from python:3.6-stretch

run apt-get update && apt-get install -y libenchant-dev libxml2-dev libxslt-dev zlib1g-dev

run pip install sqlalchemy watchdog requests bs4 pythonwhois lxml inflect geoip2 ddg3 isodate

workdir /app

copy . /app

cmd ["python", "-m", "cloudbot"]