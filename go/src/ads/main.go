package main

import "fmt"
import "os"
import "gopkg.in/yaml.v2"
import "log"
import "path/filepath"
import "io/ioutil"
import "os/exec"
import "strings"
import "sort"
import "unicode/utf8"
import "flag"

func main() {
	cwd, err := os.Getwd()
	if err != nil {
		log.Fatalf("Couldn't get working directory: %v", err)
	}

	proj, err := build_project(cwd)
	if err != nil {
		log.Fatalf("Failed to build project: %v", err)
	}

	cmd := os.Args[1]
	rest := os.Args[2:]
	switch cmd {
	case "list":
		list(proj, rest)
	case "up":
		up(proj, rest)
	case "down":
		down(proj, rest)
	case "bounce":
		down(proj, rest)
		up(proj, rest)
	case "status":
		status(proj, rest)
	case "logs":
		logs(proj, rest)
	case "dump":
		dump(proj, rest)
	default:
		usage := `usage: ads [-h] <command> [args] [service [service ...]]
		ads: error: argument <command>: invalid choice: '` + cmd + `' (choose from 'status', 'run', 'help', 'edit', 'stop', 'list', 'up', 'bounce', 'down', 'start', 'kill', 'home', 'restart', 'logs')`
		os.Stderr.Write([]byte(usage + "\n"))
		os.Exit(1)
	}
}

//-----------------------------------------------
// Project model
//-----------------------------------------------

type Project struct {
	Services map[string]Service
}

type Service struct {
	Start_cmd   string
	Stop_cmd    string
	Status_cmd  string
	Log_paths   []string
	Description string
	Name        string
	Home        string
}

func build_project(root string) (Project, error) {
	proj := Project{Services: make(map[string]Service)}

	visit := func(p string, f os.FileInfo, _ error) error {
		if f.Name() == "ads.yml" {
			contents, err := ioutil.ReadFile(p)
			if err != nil {
				return err
			}
			s := Service{}
			err = yaml.Unmarshal(contents, &s)
			if err != nil {
				return err
			}
			s.Home = filepath.Dir(p)
			s.Name = filepath.Base(s.Home)
			proj.Services[s.Name] = s
		}
		return nil
	}

	err := filepath.Walk(root, visit)
	return proj, err
}

//-----------------------------------------------
// The commands!
//-----------------------------------------------

func list(proj Project, args []string) {
	keys := sortedKeys(proj.Services)
	maxLen := 0
	for _, name := range keys {
		nameLen := utf8.RuneCountInString(name)
		if nameLen > maxLen {
			maxLen = nameLen
		}
	}
	for _, name := range keys {
		fmt.Printf("%"+string(maxLen)+"s %s", name, proj.Services[name].Description)
	}
}

func up(proj Project, args []string) {
	for _, s := range resolveOrDie(proj, args) {
		if isUpOrDie(s) {
			fmt.Println(s.Name + " is already running")
			continue
		}

		fmt.Println("Starting " + s.Name)
		err := wrapAndExec(s.Start_cmd, s.Home)
		if err != nil {
			fmt.Println("Failed to start " + s.Name)
		}
	}
}

func down(proj Project, args []string) {
	for _, s := range resolveOrDie(proj, args) {
		if !isUpOrDie(s) {
			fmt.Println(s.Name + " is already stopped")
			continue
		}

		fmt.Println("Stopping " + s.Name)
		err := wrapAndExec(s.Stop_cmd, s.Home)
		if err != nil {
			fmt.Println("Failed to stop " + s.Name)
		}
	}
}

func status(proj Project, args []string) {
	for _, s := range resolveOrDie(proj, args) {
		var label string
		if isUpOrDie(s) {
			label = "ok"
		} else {
			label = "stopped"
		}
		fmt.Printf("%s: %s\n", s.Name, label)
	}
}

func logs(proj Project, args []string) {
	fs := flag.NewFlagSet("logs", flag.ExitOnError)
	isCat := fs.Bool("cat", false, "cats shit")
	fs.Parse(args)
	args = fs.Args()

	var absLogPaths []string
	for _, s := range resolveOrDie(proj, args) {
		for _, p := range s.Log_paths {
			absLogPaths = append(absLogPaths, filepath.Join(s.Home, p))
		}
	}

	cwd, err := os.Getwd()
	if err != nil {
		log.Fatalf("Failed to get working dir: %v", err)
	}
	if *isCat {
		fmt.Printf("catting %v\n", absLogPaths)
		err = wrapAndExec("cat "+strings.Join(absLogPaths, " "), cwd)
		if err != nil {
			log.Fatalf("Failed to run cat: %v", err)
		}
	} else {
		err = wrapAndExec("tail -f "+strings.Join(absLogPaths, " "), cwd)
		if err != nil {
			log.Fatalf("Failed to run tail: %v", err)
		}
	}
}

func dump(proj Project, args []string) {
	projStr, err := yaml.Marshal(proj)
	if err != nil {
		log.Fatalf("Failed to serialize project: %v", err)
	}
	fmt.Print(string(projStr))
}

//-----------------------------------------------
// Command helpers
//-----------------------------------------------

func resolveOrDie(proj Project, names []string) []Service {
	if len(names) == 0 {
		var all []Service
		for _, s := range proj.Services {
			all = append(all, s)
		}
		return all
	}

	var services []Service
	for _, name := range names {
		s, ok := proj.Services[name]
		if !ok {
			log.Fatalf("No such service: %s\n", name)
		}
		services = append(services, s)
	}
	return services
}

func isUpOrDie(s Service) bool {
	return wrapAndExec(s.Status_cmd, s.Home) == nil
}

func wrapAndExec(bashSrc string, wdir string) error {

	launcherFd, err := ioutil.TempFile("", "ads_launcher_")
	if err != nil {
		log.Fatalf("Failed to create temp launcher file: %v", err)
	}
	launcherPath := launcherFd.Name()
	defer os.Remove(launcherPath)
	_, err = launcherFd.WriteString(bashSrc)
	if err != nil {
		log.Fatalf("Failed to write temp launcher file: %v", err)
	}
	err = launcherFd.Close()
	if err != nil {
		log.Println("Warning: failed to close temp launcher file: %v", err)
	}

	cmd := exec.Command("/bin/bash", launcherPath)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Dir = wdir
	err = cmd.Run()
	if err != nil {
		return err
	}
	return nil
}

func sortedKeys(mymap map[string]Service) []string {
	keys := make([]string, len(mymap))
	i := 0
	for k := range mymap {
		keys[i] = k
		i++
	}
	sort.Strings(keys)
	return keys
}
