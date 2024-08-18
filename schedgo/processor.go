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
	"fmt"
	"log"
	"sync"
	"time"
)

var processorLock = &sync.Mutex{}

func gatherEnergyMetrics(interval int, done chan bool, wg *sync.WaitGroup) {
	for {
		select {
		case <-time.After(time.Duration(interval) * time.Second):
			err := collectEnergyMetrics()
			if err != nil {
				log.Println(err)
			}

		case <-done:
			defer wg.Done()
			log.Println("Stopped gathering metrics")
			return
		}
	}
}

func scheduleUnscheduled(interval int, done chan bool, wg *sync.WaitGroup) {
	for {
		select {
		case <-time.After(time.Duration(interval) * time.Second):
			err := schedulePods()
			if err != nil {
				log.Println(err)
			}
		case <-done:
			defer wg.Done()
			log.Println("Stopped attempting to schedule the unscheduled")
			return
		}
	}
}

func checkUnscheduled(done chan bool, wg *sync.WaitGroup) {
	pods, errc := watchUnscheduledPods()

	for {
		select {
		case err := <-errc:
			log.Println(err)
		case pod := <-pods:
			processorLock.Lock()
			time.Sleep(2 * time.Second)
			err := schedulePod(&pod)
			if err != nil {
				log.Println(err)
			}
			processorLock.Unlock()
		case <-done:
			defer wg.Done()
			log.Println("Stopped check unscheduled loop")
			return
		}
	}
}

func schedulePod(pod *Pod) error {
	nodes, err := fit(pod)
	if err != nil {
		return err
	}
	if len(nodes) == 0 {
		fmt.Printf("FAILURE: Cannot schedule '%s' no node fulfills criteria", pod.Metadata.Name)

		return fmt.Errorf("cannot schedule '%s' no node fulfills criteria", pod.Metadata.Name)
	}
	node, err := selectNode(nodes, pod.Metadata.Name)

	if err != nil {
		return err
	}

	fmt.Printf("Success: Schedule pod '%s' on node with metadata: %#v ", pod.Metadata.Name, node.Metadata)

	err = bind(pod, node)
	if err != nil {
		return err
	}

	// bind-operations are queued to compute correcte node metrics as Scaphandre only measures data every 7 seconds
	queueBindOperation(pod.Metadata.Name, node.Metadata.Name)
	return nil
}

func schedulePods() error {
	processorLock.Lock()
	defer processorLock.Unlock()
	pods, err := getUnscheduledPods()
	if err != nil {
		return err
	}
	for _, pod := range pods {
		err := schedulePod(pod)
		if err != nil {
			log.Println(err)
		}
	}
	return nil
}
