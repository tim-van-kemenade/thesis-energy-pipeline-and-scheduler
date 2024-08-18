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
	"fmt"
)

var (
	prometheusHost = "http://192.168.221.2:9090"

	podCpuPercQuery = "scaph_process_cpu_usage_percentage"
	podWattQuery    = "scaph_process_power_consumption_microwatts"
	hostJouleQuery  = "scaph_host_energy_microjoules"
	hostWattQuery   = "scaph_host_power_microwatts"
)

func collectEnergyMetrics() error {
	time_progressed := false

	var err error
	time_progressed, err = setNodeEnergy()
	if err != nil {
		return err
	}

	// Only if the Scaphandre time has progressed for the node-data we are gooing to collect
	// a new version of the Pod data, as this is a significantly larger dataset
	if time_progressed {
		// Every 10 iterations update the pod-microWatt information
		err := updatePoddata()
		if err != nil {
			fmt.Println("Failed to update the PodMicroWatts. Error: %v\n", err)
		}
	}

	return nil
}
