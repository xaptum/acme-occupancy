FROM python:3.8.5-buster

ADD requirements.txt /
RUN pip --use-feature=2020-resolver install -r requirements.txt

ADD broker.py /
ADD monkeypatch.py /

EXPOSE 1883

ENTRYPOINT [ "python", "/broker.py" ]
