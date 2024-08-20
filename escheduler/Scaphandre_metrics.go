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
	"encoding/json"
)

type ScaphandreMetricContainer struct {
	Status string          `json:"status"`
	Data   MetricContainer `json:"data"`
}

type MetricContainer struct {
	ResultType string        `json:"resultType"`
	Result     []MetricValue `json:"result"`
}

type MetricValue struct {
	Metric Metric    `json:"metric"`
	Value  MetricVal `json:"value"`
}

type Metric struct {
	Container string `json:"container,omitempty"`
	Endpoint  string `json:"endpoint,omitempty"`
	Instance  string `json:"instance,omitempty"`
	Job       string `json:"job,omitempty"`
	Namespace string `json:"namespace,omitempty"`
	Pid       string `json:"pid,omitempty"`
	Pod       string `json:"pod,omitempty"`
	Service   string `json:"service,omitempty"`
}

type MetricVal []interface{} // first value is a timestamp epoch.millis and the second value is a metric as a string

func parseScaphandreMetric(bytes []byte) (ScaphandreMetricContainer, error) {
	// we initialize our array
	var podMetrics ScaphandreMetricContainer

	// we unmarshal our byteArray which contains our
	// jsonFile's content into 'users' which we defined above
	err := json.Unmarshal(bytes, &podMetrics)
	return podMetrics, err
}
