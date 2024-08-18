// Copyright 2024 github.com/tim-van-kemenade
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package main

import (
	"net/http"
	"github.com/patrickmn/go-cache"
	"time"
	"encoding/json"
)

var (
	prometheusHost = "192.168.221.2:9090"
	queryEndpoint = "/api/v1/query"
	// c = cache.New(5*time.Minute, 10*time.Minute)
	m = make(map[string]int) // or double?
)

func getJson(url string, target interface{}) error {
    r, err := myClient.Get(url)
    if err != nil {
        return err
    }
    defer r.Body.Close()

    return json.NewDecoder(r.Body).Decode(target)
}

func selectNode(nodes []Node) (Node, error) {
	type NodeEnergy struct {
		Node  Node
		Energy float64
	}

	var metrics TypePlaceholder

	query := url.Values{}
	query.Set("query", "")

	request := &http.Request{
		Header: make(http.Header),
		Method: http.MethodGet,
		URL: &url.URL{
			Host:     prometheusHost,
			Path:     queryEndpoint,
			RawQuery: query.Encode(),
			Scheme:   "http",
		},
	}
	request.Header.Set("Accept", "application/json, */*")

	resp, err := http.DefaultClient.Do(request)
	if err != nil {
		return Node{}, err
	}
	err = json.NewDecoder(resp.Body).Decode(&metrics)
	if err != nil {
		return Node{}, err
	}

	energyVal, ok := m[podName]

	var bestNodeEnergy *NodeEnergy
	for _, n := range nodes {
		requestUrl := "http://192.168.221.2:9090/api/v1/query?query=up"
		res, err := http.Get(requestURL)
		if err != nil {
			return Node{}, err
		}
		if bestNodeEnergy == nil {
			bestNodeEnergy = &NodeEnergy{n, nodeEnergy}
			continue
		}
		if nodeEnergy < bestNodeEnergy.Energy {
			bestNodeEnergy.Node = n
			bestNodeEnergy.Energy = nodeEnergy
		}
	}

	if bestNodeEnergy == nil {
		bestNodeEnergy = &NodeEnergy{nodes[0], 0}
	}
	return bestNodeEnergy.Node, nil
}
