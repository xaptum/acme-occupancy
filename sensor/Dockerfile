FROM python:3.7.9-stretch

ADD requirements.txt /
RUN pip --use-feature=2020-resolver install -r requirements.txt

ADD sensor.py /

ENTRYPOINT [ "python", "/sensor.py" ]
