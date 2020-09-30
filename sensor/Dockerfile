FROM python:3.8.5-buster

ADD requirements.txt /
RUN pip --use-feature=2020-resolver install -r requirements.txt

ADD sensor.py /

ENTRYPOINT [ "python", "/sensor.py" ]
