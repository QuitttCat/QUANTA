package wqfm.tools;

import java.io.BufferedReader;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.Map;
import java.util.stream.Collectors;
import wqfm.algo.FMComputer;
import wqfm.bip.Bipartition_8_values;
import wqfm.bip.InitialBipartition;
import wqfm.configs.DefaultValues;
import wqfm.ds.CustomDSPerLevel;
import wqfm.ds.FMResultObject;
import wqfm.ds.InitialTable;
import wqfm.ds.Quartet;
import wqfm.utils.Helper;

public class OneStepPartition {

    public static void main(String[] args) {
        if (args.length < 3) {
            System.out.println("Usage: OneStepPartition <input_wqrts> <left_out> <right_out>");
            System.exit(-1);
        }

        String inputFile = args[0];
        String leftOut = args[1];
        String rightOut = args[2];

        InitialTable initialTable = new InitialTable();
        CustomDSPerLevel customDS = new CustomDSPerLevel();

        readFileAndPopulateInitialTables(inputFile, customDS, initialTable);

        customDS.setInitialTableReference(initialTable);
        customDS.sortQuartetIndicesMap();
        customDS.fillRelevantQuartetsMap();
        customDS.fillUpTaxaList();

        int level = 1;
        InitialBipartition initialBip = new InitialBipartition();
        Map<Integer, Integer> mapInitialBipartition = initialBip.getInitialBipartitionMap(customDS);

        Bipartition_8_values initialBip8Vals = new Bipartition_8_values();
        initialBip8Vals.compute8ValuesUsingAllQuartets_this_level(customDS, mapInitialBipartition);

        FMComputer fmComputerObject = new FMComputer(customDS, mapInitialBipartition, initialBip8Vals, level);
        FMResultObject fmResultObject = fmComputerObject.run_FM_Algorithm_Whole();

        String leftContent = fmResultObject.customDS_left_partition.quartet_indices_list_unsorted
                .stream()
                .map(idx -> fmResultObject.customDS_left_partition.initial_table1_of_list_of_quartets.get(idx).getNamedQuartet())
                .collect(Collectors.joining("\n"));

        String rightContent = fmResultObject.customDS_right_partition.quartet_indices_list_unsorted
                .stream()
                .map(idx -> fmResultObject.customDS_right_partition.initial_table1_of_list_of_quartets.get(idx).getNamedQuartet())
                .collect(Collectors.joining("\n"));

        Helper.writeToFile(leftContent, leftOut);
        Helper.writeToFile(rightContent, rightOut);
    }

    private static int countChars_in_String(String str, char c) {
        int count = 0;
        for (int i = 0; i < str.length(); i++) {
            if (str.charAt(i) == c) {
                count++;
            }
        }
        return count;
    }

    private static void populatePerInputLine(CustomDSPerLevel customDS, InitialTable initialTable, String line, int line_cnt) {
        int cnt_left_brackets = countChars_in_String(line, '(');
        int cnt_right_brackets = countChars_in_String(line, ')');

        if ((cnt_left_brackets != cnt_right_brackets) || (cnt_left_brackets != 3) || (cnt_right_brackets != 3)) {
            System.out.println("\n\n****** Found STAR, line num " + line_cnt + " :->" + line);
            System.out.println("\nCan't handle polytomy for now. Exiting System.\n\n");
            System.exit(-1);
        }

        Quartet quartet = new Quartet(line);
        initialTable.addToListOfQuartets(quartet);
        int idx_qrt_in_table_1 = initialTable.sizeTable() - 1;
        customDS.quartet_indices_list_unsorted.add(idx_qrt_in_table_1);
    }

    private static void readFileAndPopulateInitialTables(String inputFileName, CustomDSPerLevel customDS, InitialTable initialTable) {
        FileInputStream fileInputStream = null;
        try {
            fileInputStream = new FileInputStream(inputFileName);
            InputStreamReader inputStreamReader = new InputStreamReader(fileInputStream);
            try (BufferedReader bufferedReader = new BufferedReader(inputStreamReader)) {
                String line;
                int line_cnt = 1;
                while ((line = bufferedReader.readLine()) != null && !line.isEmpty()) {
                    populatePerInputLine(customDS, initialTable, line, line_cnt);
                    line_cnt++;
                }
            }
        } catch (IOException ex) {
            System.out.println("ERROR READING FILE <" + inputFileName + ">. EXITING SYSTEM");
            System.exit(-1);
        } finally {
            if (fileInputStream != null) {
                try {
                    fileInputStream.close();
                } catch (IOException ex) {
                    System.out.println("ERROR IN CLOSING fileInputStream while reading file. Exiting");
                    System.exit(-1);
                }
            }
        }
    }
}
