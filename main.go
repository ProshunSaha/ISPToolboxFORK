package main

import (
    "fmt"
	"os/exec"
	"net/http"
	"strings"
	"encoding/json"
	"strconv"
)

type RFSimMetaDataResponse struct {
	File string
	BoundingBox [4]float64
}

/* /home/ec2-user/Signal-Server/signalserverHD -sdf /home/ec2-user/efs -lat 51.849 -lon -2.2299 -txh 25 -f 450 -erp 20 -rxh 2 -rt 10 -o test2 -R 10 -res 3600 -pm 3 */
const SignalServerBinaryPath = "/home/ec2-user/Signal-Server/signalserverHD"
const SDFFilePath = "/home/ec2-user/efs"
const OutputArg = "/home/ec2-user/output/test"
const ConvertPath = "/usr/bin/convert"

func serveRFRequest(writer http.ResponseWriter, request *http.Request) {
	var LatArg = "51.849"
	var LngArg = "-2.2299"
	var TxHArg = "25"
	var FreqArg = "450"
	var ErpArg = "20"
	var RxHArg = "2"
	var RtArg = "10"
	var RArg = "10"
	var ResArg = "3600"
	var PmArg = "3"
	/* Get GET Parameters from URL*/
	for k, v := range request.URL.Query() {
		switch k {
		case "lat":
			LatArg = v[0]
		case "lng":
			LngArg = v[0]
		case "txh":
			TxHArg = v[0]
		case "freq":
			FreqArg= v[0]
		case "Erp":
			ErpArg= v[0]
		case "Rx":
			RxHArg= v[0]
		case "Rt":
			RtArg= v[0]
		case "R":
			RArg= v[0]
		case "Res":
			ResArg= v[0]
		case "Pm":
			PmArg= v[0]
		default:
			fmt.Println("Unknown argument:" + k + "|" + (v[0]))
		}
	}
	Args := []string{"-sdf", SDFFilePath, "-lat", LatArg, "-lon", LngArg, "-txh", TxHArg, "-f", FreqArg, "-erp", ErpArg, "-rxh", RxHArg, "-rt",RtArg, "-o",OutputArg, "-R", RArg, "-res",ResArg, "-pm", PmArg}
	fmt.Printf("%#v\n", Args)

	/* Run Request through signal server */
	fmt.Println("Running RF Simulation")
    output, err := exec.Command(SignalServerBinaryPath, Args...).CombinedOutput()
    if err!=nil {
        fmt.Println(err.Error())
	}
	boundingBox := strings.SplitN(string(output),"|",-1)
	var boundingBoxFloat [4]float64
	var j = 0
	for i := 0; i < len(boundingBox); i++ {
		fmt.Println(boundingBox[i])
		f, err := strconv.ParseFloat(boundingBox[i], 64)
		if err == nil && j < 4 {
			boundingBoxFloat[j] = f
			j++
		}
	}

	/* Convert from ppm to png */
	fmt.Println("Converting output to png")
	ConvertArgs := []string{OutputArg+".ppm", OutputArg+".png"}
	outputConvert, errConvert := exec.Command(ConvertPath, ConvertArgs...).CombinedOutput()

    if err!=nil {
        fmt.Println(errConvert.Error())
	}
	fmt.Println(outputConvert)
	metadataResponse := RFSimMetaDataResponse{"", boundingBoxFloat}
	js, err := json.Marshal(metadataResponse)
	if err != nil {
		http.Error(writer, err.Error(), http.StatusInternalServerError)
		return
	}

	writer.Header().Set("Content-Type", "application/json")
	writer.Write(js)
}

func serveRFFile(writer http.ResponseWriter, request *http.Request) {
	/* Get GET Parameters from URL*/
	var FileArg = ""
	for k, v := range request.URL.Query() {
		switch k {
		case "file":
			FileArg = v[0]
		default:
			fmt.Println("Unknown argument:" + k + "|" + (v[0]))
		}
	}
	/* Security: ServeFile removes '..' from paths*/
	http.ServeFile(writer, request, OutputArg + FileArg + ".png")
}

func main() {
	fmt.Println("Starting RF Coverage WebServer")
	http.HandleFunc("/coverage-request/", serveRFRequest)
	http.HandleFunc("/coverage-file/", serveRFFile)
	http.ListenAndServe(":80", nil)
}