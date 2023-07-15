package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/jackc/pgx" // sudo go get -u github.com/jackc/pgx
)

type RFSimMetaDataResponse struct {
	File        string
	BoundingBox [4]float64
}

/* /home/ec2-user/Signal-Server/signalserverHD -sdf /home/ec2-user/efs -lat 51.849 -lon -2.2299 -txh 25 -f 450 -erp 20 -rxh 2 -rt 10 -o test2 -R 10 -res 3600 -pm 3 */
const SignalServerBinaryPath = "/home/ec2-user/Signal-Server/signalserverHD"
const SDFFilePath = "/home/ec2-user/efs"
const OutputArg = "/home/ec2-user/output/"
const ConvertPath = "/usr/bin/convert"
const StaticFilePathTest = "/home/ec2-user/RFCoverageWebServer/static/"
const SpeedTestFilePathTest = "/home/ec2-user/RFCoverageWebServer/speedtest/"
const SpeedTestDevFilePathTest = "/home/ec2-user/RFCoverageWebServer/speedtestdev/"
const LidarFilePathTest = "/home/ec2-user/RFCoverageWebServer/lidarviewer/"

const AccessControlAllowOriginURLS = "*"

const AccessControlAllowOriginURLSQuery = "https://www.facebook.com"
const AccessControlAllowOriginURLSSuffix = "facebook.com"

func serveRFRequest(writer http.ResponseWriter, request *http.Request) {
	writer.Header().Set("Access-Control-Allow-Origin", AccessControlAllowOriginURLS)
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
			FreqArg = v[0]
		case "Erp":
			ErpArg = v[0]
		case "rxh":
			RxHArg = v[0]
		case "Rt":
			RtArg = v[0]
		case "R":
			RArg = v[0]
		case "Res":
			ResArg = v[0]
		case "Pm":
			PmArg = v[0]
		default:
			fmt.Println("Unknown argument:" + k + "|" + (v[0]))
		}
	}
	/*Create Temporary File*/
	file, err := ioutil.TempFile(OutputArg, "output-*")
	if err != nil {
		fmt.Println(err)
		return
	}
	Args := []string{"-sdf", SDFFilePath, "-lat", LatArg, "-lon", LngArg, "-txh", TxHArg, "-f", FreqArg, "-erp", ErpArg, "-rxh", RxHArg, "-rt", RtArg, "-o", file.Name(), "-R", RArg, "-res", ResArg, "-pm", PmArg}
	fmt.Printf("%#v\n", Args)

	/* Run Request through signal server */
	fmt.Println("Running RF Simulation")
	output, err := exec.Command(SignalServerBinaryPath, Args...).CombinedOutput()
	if err != nil {
		fmt.Println(err.Error())
	}
	boundingBox := strings.SplitN(string(output), "|", -1)
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
	ConvertArgs := []string{file.Name() + ".ppm", file.Name() + ".png"}
	outputConvert, errConvert := exec.Command(ConvertPath, ConvertArgs...).CombinedOutput()

	if err != nil {
		fmt.Println(errConvert.Error())
	}
	fmt.Println(outputConvert)
	metadataResponse := RFSimMetaDataResponse{filepath.Base(file.Name()), boundingBoxFloat}
	js, err := json.Marshal(metadataResponse)
	if err != nil {
		http.Error(writer, err.Error(), http.StatusInternalServerError)
		return
	}

	writer.Header().Set("Content-Type", "application/json")
	writer.Write(js)
}

func serveRFFileHandler(writer http.ResponseWriter, request *http.Request) {
	writer.Header().Set("Access-Control-Allow-Origin", AccessControlAllowOriginURLS)
	/* Get GET Parameters from URL*/
	for k, v := range request.URL.Query() {
		switch k {
		default:
			fmt.Println("Unknown argument:" + k + "|" + (v[0]))
		}
	}
	/* Security: ServeFile removes '..' from paths */
	fmt.Println(request.URL.Path[len("/coverage-file/"):])
	http.ServeFile(writer, request, OutputArg+request.URL.Path[len("/coverage-file/"):])
}

func serveStatusOk(writer http.ResponseWriter, request *http.Request) {
	writer.Header().Set("Access-Control-Allow-Origin", AccessControlAllowOriginURLS)
	writer.WriteHeader(http.StatusOK)
}

/**********************************************/
/* Market Sizing API + Connection to Database */
/**********************************************/
const (
	host     = "microsoft-building-footprints.cedcz50bv5p9.us-east-2.rds.amazonaws.com"
	port     = 5432
	user     = "fbcmasteruser"
	dbname   = "postgres"
)

type MarketSizingIncomeResponse struct {
	Error           int        `json:"error"`
	AvgIncome    	float32    `json:"avgincome"`
	AvgError 		float32    `json:"avgerror"`
}

func serveMarketSizingIncomeRequest(writer http.ResponseWriter, request *http.Request) {
	if(strings.HasSuffix(request.Header.Get("Origin"), AccessControlAllowOriginURLSSuffix)) {
		writer.Header().Set("Access-Control-Allow-Origin", request.Header.Get("Origin"))
	}
	/* Get GET Parameters from URL*/
	var coords = ""
	for k, v := range request.URL.Query() {
		switch k {
		case "coordinates":
			coords = v[0]
		default:
			fmt.Println("Unknown argument:" + k + "|" + (v[0]))
		}
	}
	coords2 := strings.Split(coords, "%2C")
	var coords3 = ""
	if len(coords2) > 0 {
		coords3 = coords2[0]
	}
	for i := 1; i < len(coords2); i++ {
		var sep = ","
		if (i % 2) != 0 {
			sep = " "
		}
		coords3 += sep + coords2[i]
	}
	coord_query := "POLYGON((" + coords3 + "))"

	/* PGX Connection */
	dsn := "host=" + host + " user=" + user + " password=" + password + " dbname=" + dbname + " port=" + strconv.Itoa(port)
	conn, err := pgx.Connect(context.Background(), dsn)
	if err != nil {
		panic(err)
	}
	defer conn.Close(context.Background())
	println(coord_query)

	rows, QueryErr := conn.Query(context.Background(), "SELECT AVG(tract.income2018) AS avg_income, AVG(tract.error2018) AS avg_error FROM (SELECT * FROM (SELECT * FROM microsoftfootprints WHERE ST_Intersects(microsoftfootprints.geog, $1)) AS intersecting_footprints  LEFT JOIN microsoftfootprint2tracts ON intersecting_footprints.gid = microsoftfootprint2tracts.footprintgid) AS intersecting_footprints_mapped LEFT JOIN tract on intersecting_footprints_mapped.tractgids[1]=tract.gid;", coord_query)
	if QueryErr != nil {
		panic(QueryErr)
	}
	defer rows.Close()
	var avg_income float32
	var avg_error  float32
	for rows.Next() {
		err = rows.Scan(&avg_income, &avg_error)
		if err != nil {
			panic(err)
		}

	}
	response := MarketSizingIncomeResponse {
		Error:            0,
		AvgIncome:    	avg_income,
		AvgError:  avg_error,
	}
	if err := json.NewEncoder(writer).Encode(response); err != nil {
		panic(err)
	}
	writer.Header().Set("Content-Type", "application/json")
}

type MarketSizingResponse struct {
	Error            int      `json:"error"`
	Numbuildings     int      `json:"numbuildings"`
	BuildingPolygons []string `json:"polygons"`
}

func serveMarketSizingRequest(writer http.ResponseWriter, request *http.Request) {
	if(strings.HasSuffix(request.Header.Get("Origin"), AccessControlAllowOriginURLSSuffix)) {
		writer.Header().Set("Access-Control-Allow-Origin", request.Header.Get("Origin"))
	}
	/* Get GET Parameters from URL*/
	var coords = ""
	for k, v := range request.URL.Query() {
		switch k {
		case "coordinates":
			coords = v[0]
		default:
			fmt.Println("Unknown argument:" + k + "|" + (v[0]))
		}
	}
	coords2 := strings.Split(coords, "%2C")
	var coords3 = ""
	if len(coords2) > 0 {
		coords3 = coords2[0]
	}
	for i := 1; i < len(coords2); i++ {
		var sep = ","
		if (i % 2) != 0 {
			sep = " "
		}
		coords3 += sep + coords2[i]
	}
	coord_query := "POLYGON((" + coords3 + "))"

	/* PGX Connection */
	dsn := "host=" + host + " user=" + user + " password=" + password + " dbname=" + dbname + " port=" + strconv.Itoa(port)
	conn, err := pgx.Connect(context.Background(), dsn)
	if err != nil {
		panic(err)
	}
	defer conn.Close(context.Background())

	rows, QueryErr := conn.Query(context.Background(), "SELECT gid, us_state, ST_AsGeoJSON(geog) FROM microsoftfootprints WHERE ST_Intersects(geog, $1);", coord_query)
	if QueryErr != nil {
		panic(QueryErr)
	}
	defer rows.Close()
	var sum = 0
	var polygons []string
	for rows.Next() {
		var n int32
		var state string
		var polygon string
		err = rows.Scan(&n, &state, &polygon)
		if err != nil {
			panic(err)
		}
		sum += 1
		polygons = append(polygons, polygon)
	}
	response := MarketSizingResponse{
		Error:            0,
		Numbuildings:     sum,
		BuildingPolygons: polygons,
	}
	if err := json.NewEncoder(writer).Encode(response); err != nil {
		panic(err)
	}
	writer.Header().Set("Content-Type", "application/json")
}

func main() {
	fmt.Println("Starting RF Coverage WebServer")
	staticfs := http.FileServer(http.Dir(StaticFilePathTest))
	speedtestfs := http.FileServer(http.Dir(SpeedTestFilePathTest))
	speedtestdevfs := http.FileServer(http.Dir(SpeedTestDevFilePathTest))
	lidarfs := http.FileServer(http.Dir(LidarFilePathTest))

	http.HandleFunc("/market-income/", serveMarketSizingIncomeRequest);
	http.HandleFunc("/coverage-request/", serveRFRequest)
	http.HandleFunc("/coverage-file/", serveRFFileHandler)
	http.HandleFunc("/market-size/", serveMarketSizingRequest)
	http.Handle("/static/", http.StripPrefix("/static/", staticfs))
	http.Handle("/speedtest/", http.StripPrefix("/speedtest/", speedtestfs))
	http.Handle("/speedtestdev/", http.StripPrefix("/speedtestdev/", speedtestdevfs))
	http.Handle("/lidarviewer/", http.StripPrefix("/lidarviewer/", lidarfs))

	http.HandleFunc("/", serveStatusOk)
	http.ListenAndServe(":80", nil)
}
