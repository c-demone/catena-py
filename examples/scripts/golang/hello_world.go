package main

import (
		"fmt"
	    "github.com/ilyakaznacheev/cleanenv"
	   )


type HelloName struct {
	Name     string `env:"NAME" env-default:"world"`
}

func main() {

	    // read environment variables
		var cfg HelloName
        cleanenv.ReadEnv(&cfg)

		// build message to print
		msg := "Hello "
		msg += cfg.Name
		msg += "!"

		fmt.Println(msg)
		fmt.Sprintf("Hello %s!", cfg.Name)
}