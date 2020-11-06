FROM sensor

# Install the Xaptum APT GPG key
RUN apt-get update  && \
    apt-get install -y --no-install-recommends      \
      gnupg                                         \
      dirmngr                                    && \
    apt-key adv --keyserver keyserver.ubuntu.com    \
                --recv-keys c615bfaa7fe1b4ca     && \
    apt-get remove -y                               \
      gnupg                                         \
      dirmngr                                    && \
    rm -rf /var/lib/apt/lists/*

# Install the Xaptum APT repo
COPY xaptum.list /etc/apt/sources.list.d/xaptum.list

# Install required packages
RUN apt-get update  && \
    apt-get install -y --no-install-recommends      \
      enftun                                        \
      iproute2                                   && \
    rm -rf /var/lib/apt/lists/*

# Install enftun configuration
COPY enf0.conf /etc/enftun/enf0.conf

# Configure entrypoint script
COPY entrypoint.sh /usr/local/bin/
RUN ln -s usr/local/bin/entrypoint.sh / # backwards compat
ENTRYPOINT ["entrypoint.sh"]
