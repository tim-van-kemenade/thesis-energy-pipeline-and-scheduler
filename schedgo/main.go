// Copyright 2016 Google Inc. All Rights Reserved.
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
	"log"
	"os"
	"os/signal"
	"sync"
	"syscall"
)

const schedulerName = "kubepower"

func main() {

	log.Println("Starting KubePowerSched")

	done := make(chan bool)
	var wg sync.WaitGroup

	wg.Add(1)
	go gatherEnergyMetrics(1, done, &wg)
	wg.Add(1)
	go checkUnscheduled(done, &wg)
	wg.Add(1)
	go scheduleUnscheduled(30, done, &wg)

	signalChan := make(chan os.Signal, 1)
	signal.Notify(signalChan, syscall.SIGINT, syscall.SIGTERM)
	for {
		select {
		case <-signalChan:
			log.Printf("Stopping KubePowerSched")
			done <- true
			wg.Wait()
			os.Exit(0)
		}
	}
}
