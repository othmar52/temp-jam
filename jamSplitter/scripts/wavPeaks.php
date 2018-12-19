<?php

$args = getopt("i:n::");

if (array_key_exists('i', $args) === FALSE) {
    echo "missing argument -i for input wav file\n";
    exit(1);
}
$filePath = $args['i'];
if (is_file(realpath($filePath)) === FALSE) {
    echo "argument -i is no valid file\n";
    exit(2);
}
$filePath = realpath($filePath);
if (is_readable($filePath) === FALSE) {
    echo "file is not readable\n";
    exit(3);
}
$defaultAmount = 2000;
$n = (array_key_exists('n', $args) === FALSE)
    ? $defaultAmount
    : (( (int)$args['n'] > 0 ) ? (int)$args['n'] : $defaultAmount) ;





$data = getWavPeaks($filePath);
# for some reason the very first entry has a very high peak!?
array_shift($data);
#echo join(",", $data);exit;
echo join(",", beautifyPeaks(limitArray($data, $n))) . "\n";

exit(0);

function getWavPeaks($temp_wav) {
        ini_set ("memory_limit", "1024M"); // extracted wav-data is very large (500000 entries)
        /**
         * Below as posted by "zvoneM" on
         * http://forums.devshed.com/php-development-5/reading-16-bit-wav-file-318740.html
         * as findValues() defined above
         * Translated from Croation to English - July 11, 2011
         */
        $data = array();
        #echo $temp_wav; exit;
        $handle = fopen ($temp_wav, "r");
        //dohvacanje zaglavlja wav datoteke
        $heading[] = fread ($handle, 4);
        $heading[] = bin2hex(fread ($handle, 4));
        $heading[] = fread ($handle, 4);
        $heading[] = fread ($handle, 4);
        $heading[] = bin2hex(fread ($handle, 4));
        $heading[] = bin2hex(fread ($handle, 2));
        $heading[] = bin2hex(fread ($handle, 2));
        $heading[] = bin2hex(fread ($handle, 4));
        $heading[] = bin2hex(fread ($handle, 4));
        $heading[] = bin2hex(fread ($handle, 2));
        $heading[] = bin2hex(fread ($handle, 2));
        $heading[] = fread ($handle, 4);
        $heading[] = bin2hex(fread ($handle, 4));

        //bitrate wav datoteke
        $peek = hexdec(substr($heading[10], 0, 2));
        $byte = $peek / 8;

        //provjera da li se radi o mono ili stereo wavu
        $channel = hexdec(substr($heading[6], 0, 2));

        $ratio = ($channel == 2) ? 40 : 80;

        while(!feof($handle)) {
            $bytes = array();
            //get number of bytes depending on bitrate
            for ($i = 0; $i < $byte; $i++) {
                $bytes[$i] = fgetc($handle);
            }
            if($byte === 1) {
                getValue8BitWav($data, $bytes);
            }
            if($byte === 2) {
                getValue16BitWav($data, $bytes);
            }
            //skip bytes for memory optimization
            fread ($handle, $ratio);
        }

        // close and cleanup
        fclose ($handle);
        return $data;
    }
    function findValues($byte1, $byte2) {
        $byte1 = hexdec(bin2hex($byte1));
        $byte2 = hexdec(bin2hex($byte2));
        return ($byte1 + ($byte2*256));
    }
    function getValue8BitWav(&$data, $bytes) {
        $value = findValues($bytes[0], $bytes[1]) - 128;
        $data[]= ($value < 0) ? 0 : $value;
    }

    function getValue16BitWav(&$data, $bytes) {
        $temp = (ord($bytes[1]) & 128) ? 0 : 128;
        $temp = chr((ord($bytes[1]) & 127) + $temp);
        $value = floor(findValues($bytes[0], $temp) / 256) - 128;
        $data[]= ($value < 0) ? 0 : $value;
    }

    function limitArray($input, $max = 2000) {
        ini_set ("memory_limit", "1024M"); // extracted wav-data is very large (500000 entries)
        $count = count($input);
        if($count < $max) {
            return $input;
        }
        $floor = (floor($count / $max)) + 1;

        $output = array();
        $prev = 0;
        $current = 0;

        for($idx = 0; $idx < $count; $idx++) {
            $current++;
            $prev = ($input[$idx] > $prev) ? $input[$idx] : $prev;
            if($current == $floor) {
                $output[] = $prev;
                $current = 0;
                $prev = 0;
            }
            unset($input[$idx]);
        }
        return $output;
    }

    function beautifyPeaks($input) {
        $beauty = array();
        $avg = array_sum($input)/count($input);
        $maxPeak = max($input);

        // results of visual testing with dozens of random files
        // maxPeak:128 ->    best multiplicator -> 1.4
        // maxPeak:82    ->    best multiplicator -> 2.3

        // that gives us those guiding values
        // maxPeak: 128 -> 1.4
        // maxPeak: 1     -> 4

        // now try to find the best multiplicator for ($maxPeak/$avg) by playing around...
        $multiMax = 3.3;
        $multiMin = 1.4;
        $multi100th = ($multiMax-$multiMin)/100;

        $rangeMax = 128;
        $range100th = $rangeMax/100;
        $invertedRangePercent = 100 - $maxPeak / $range100th;
        $multiplicator = $multiMin + $invertedRangePercent * $multi100th;
        foreach($input as $value) {
            if($value < 1) {
                $beauty[] = $value;
                continue;
            }
            $beauty[] = floor($value * ($maxPeak/$avg) * $multiplicator);
        }
        return $beauty;
    }
