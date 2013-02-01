/*
 * Copyright 2012 Mozilla Foundation
 *
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package com.mozilla.fhr.pig.eval;

import java.io.IOException;
import java.util.Calendar;

import org.apache.pig.EvalFunc;
import org.apache.pig.data.Tuple;

public class ProfileCreationTime extends EvalFunc<Long> {

    public static enum ERRORS { DateParseError };

    private Calendar cal;
    
    public ProfileCreationTime() {
        cal = Calendar.getInstance();
    }
    
    @Override
    public Long exec(Tuple input) throws IOException {
        if (input == null || input.size() == 0 || 
            input.get(0) == null) {
            return null;
        }

        // reset to epoch
        cal.setTimeInMillis(0);
        // profileCreation is in days since epoch
        cal.add(Calendar.DATE, ((Number)input.get(0)).intValue());
             
        return cal.getTimeInMillis();
    }

}
