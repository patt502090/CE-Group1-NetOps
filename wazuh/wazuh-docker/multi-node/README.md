# Deploy Wazuh with Podman in multi node configuration

This deployment is defined in the `docker-compose.yml` file with two Wazuh manager containers, three Wazuh indexer containers, and one Wazuh dashboard container. It can be deployed by following these steps: 

1) Increase max_map_count on your host (Linux). This command must be run with root permissions:
```
$ sysctl -w vm.max_map_count=262144
```
2) Run the certificate creation script:
```
$ podman-compose -f generate-indexer-certs.yml run --rm generator
```
3) Start the environment with podman-compose:

- In the foregroud:
```
$ podman-compose up
```

- In the background:
```
$ podman-compose up -d
```


The environment takes about 1 minute to get up (depending on your host) for the first time since Wazuh Indexer must be started for the first time and the indexes and index patterns must be generated.
